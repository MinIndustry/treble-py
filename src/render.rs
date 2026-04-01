use rustic::Note;
use rustic::core::graph::{SimpleSink, System};

use crate::registry::{build_filter, build_source};
use crate::spec::GraphSpec;

fn check_source_index(idx: usize, system: &System) -> Result<(), String> {
    if system.sources_len() <= idx {
        Err(format!(
            "Source index `{idx}` does not correspond to any source (system contains {} source(s))",
            system.sources_len()
        ))
    } else {
        Ok(())
    }
}

fn check_filter_index<T>(idx: usize, node_map: &[T]) -> Result<(), String> {
    if node_map.len() <= idx {
        Err(format!(
            "Filter index `{idx}` does not correspond to any filter (system contains {} filter(s))",
            node_map.len()
        ))
    } else {
        Ok(())
    }
}

/// Perform a headless offline render of a `GraphSpec`.
///
/// Returns interleaved stereo frames: `Vec<[f32; 2]>` with exactly
/// `(spec.duration * spec.sample_rate).ceil()` entries.
pub fn render_graph(spec: &GraphSpec) -> Result<Vec<[f32; 2]>, String> {
    let mut system = System::new().with_block_size(spec.block_size);
    let mut source_indices: Vec<usize> = vec![];

    for source in spec.sources.iter() {
        source_indices.push(system.add_source(build_source(source, spec.sample_rate)));
    }

    let sink_idx = system.add_sink(Box::new(SimpleSink::new()));

    if spec.filters.is_empty() {
        for source_index in source_indices.iter() {
            system.connect_source_to_sink(*source_index, sink_idx);
        }
    } else {
        let nodes = spec
            .filters
            .iter()
            .map(|fs| build_filter(fs, spec.sample_rate).map(|f| system.add_filter(f)))
            .collect::<Result<Vec<_>, _>>()?;

        for connection in &spec.connections {
            match connection {
                crate::spec::ConnectionType::SourceSink { source, sink } => {
                    check_source_index(*source, &system)?;
                    system.connect_source_to_sink(*source, *sink);
                }
                crate::spec::ConnectionType::FilterSink { filter, sink } => {
                    check_filter_index(*filter, &nodes)?;
                    system.connect_sink(nodes[*filter], *sink, 0);
                }
                crate::spec::ConnectionType::SourceFilter { source, filter } => {
                    check_filter_index(*filter, &nodes)?;
                    check_source_index(*source, &system)?;
                    system.connect_source(*source, nodes[*filter], 0);
                }
                crate::spec::ConnectionType::FilterFilter {
                    filter_out,
                    filter_in,
                } => {
                    check_filter_index(*filter_out, &nodes)?;
                    check_filter_index(*filter_in, &nodes)?;
                    system.connect(nodes[*filter_out], nodes[*filter_in], 0, 0);
                }
            }
        }
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
            for source in source_indices.iter() {
                system.start_note(*source, note, 1.0);
            }
        }
        if i == note_off_block {
            for source in source_indices.iter() {
                system.stop_note(*source, note);
            }
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
