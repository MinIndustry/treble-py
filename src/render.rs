use rustic::Note;
use rustic::core::graph::{SimpleSink, System};

use crate::registry::{build_filter, build_source};
use crate::spec::GraphSpec;

/// Perform a headless offline render of a `GraphSpec`.
///
/// Returns interleaved stereo frames: `Vec<[f32; 2]>` with exactly
/// `(spec.duration * spec.sample_rate).ceil()` entries.
pub fn render_graph(spec: &GraphSpec) -> Result<Vec<[f32; 2]>, String> {
    let mut system = System::new().with_block_size(spec.block_size);

    let src_idx = system.add_source(build_source(&spec.source, spec.sample_rate));
    let sink_idx = system.add_sink(Box::new(SimpleSink::new()));

    if spec.filters.is_empty() {
        system.connect_source_to_sink(src_idx, sink_idx);
    } else {
        let nodes = spec
            .filters
            .iter()
            .map(|fs| build_filter(fs, spec.sample_rate).map(|f| system.add_filter(f)))
            .collect::<Result<Vec<_>, _>>()?;

        system.connect_source(src_idx, nodes[0], 0);
        for i in 1..nodes.len() {
            system.connect(nodes[i - 1], nodes[i], 0, 0);
        }
        system.connect_sink(*nodes.last().unwrap(), sink_idx, 0);
    }

    system
        .compute()
        .map_err(|e| format!("Graph compile error: {e:?}"))?;

    let note = Note::from_midi(spec.note);
    let note_on_block = (spec.note_on * spec.sample_rate / spec.block_size as f32) as usize;
    let note_off_block = (spec.note_off * spec.sample_rate / spec.block_size as f32) as usize;
    let total_blocks =
        (spec.duration * spec.sample_rate / spec.block_size as f32).ceil() as usize + 1;

    let mut frames: Vec<[f32; 2]> = Vec::with_capacity(total_blocks * spec.block_size);

    for i in 0..total_blocks {
        if i == note_on_block {
            system.start_note(src_idx, note, 1.0);
        }
        if i == note_off_block {
            system.stop_note(src_idx, note);
        }
        system.run();
        if let Ok(sink) = system.get_sink(sink_idx) {
            frames.extend_from_slice(&sink.consume());
        }
    }

    let target = (spec.duration * spec.sample_rate).ceil() as usize;
    frames.truncate(target);
    Ok(frames)
}
