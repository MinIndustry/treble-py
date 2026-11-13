use std::sync::Arc;

use treble::Note;
use treble::core::graph::{Entry, Sink, System};
use treble::core::{Block, Frame};

use crate::registry::{build_filter, build_source};
use crate::spec::GraphSpec;

/// Sink that sums every block pushed to it during one `System::run`.
///
/// The graph pushes one block per incoming wire. `SimpleSink` appends them, so a
/// sink fed by several sources or terminal filters received their blocks one
/// after another in time rather than mixed. Filters already sum their inputs;
/// this gives the sink the same semantics.
#[derive(Clone, Debug, Default)]
struct MixSink {
    values: Vec<Frame>,
}

impl Entry for MixSink {
    fn push(&mut self, block: Arc<Block>, _port: usize) {
        if self.values.len() < block.len() {
            self.values.resize(block.len(), [0.0; 2]);
        }
        for (acc, frame) in self.values.iter_mut().zip(block.iter()) {
            acc[0] += frame[0];
            acc[1] += frame[1];
        }
    }
}

impl Sink for MixSink {
    fn consume(&mut self) -> Block {
        std::mem::take(&mut self.values)
    }

    fn get_frames(&self) -> &[Frame] {
        &self.values
    }

    fn into_entry(self) -> Box<dyn Entry> {
        Box::new(self)
    }
}

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

    let sink_idx = system.add_sink(Box::new(MixSink::default()));

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

#[cfg(test)]
mod tests {
    use super::*;

    /// Two sources, each through its own unity-gain filter; `to_sink` lists
    /// which filters are wired to the sink.
    fn spec(to_sink: &[usize]) -> GraphSpec {
        let env = serde_json::json!({"attack": [0.01, 1.0, 0.0, 0.0], "decay": [0.1, 0.8, 0.0, 1.0],
            "sustain": 0.8, "release": [0.1, 0.0, 0.0, 0.0]});
        let sources: Vec<_> = ["sine", "saw"]
            .iter()
            .map(|w| {
                serde_json::json!({"sources": [{"waveform": w, "envelope": env}],
                "base_frequency": 440.0, "mix_mode": "Average", "glob_ampl": env})
            })
            .collect();
        let mut connections = vec![
            serde_json::json!({"SourceFilter": {"source": 0, "filter": 0}}),
            serde_json::json!({"SourceFilter": {"source": 1, "filter": 1}}),
        ];
        for f in to_sink {
            connections.push(serde_json::json!({"FilterSink": {"filter": f, "sink": 0}}));
        }
        let gain = serde_json::json!({"type": "GainFilter", "params": {"factor": 1.0}});
        serde_json::from_value(serde_json::json!({
            "note": 60, "note_on": 0.0, "note_off": 0.3, "duration": 0.5,
            "sources": sources, "filters": [gain, gain], "connections": connections,
        }))
        .unwrap()
    }

    #[test]
    fn sink_sums_its_inputs_instead_of_concatenating_them() {
        let a = render_graph(&spec(&[0])).unwrap();
        let b = render_graph(&spec(&[1])).unwrap();
        let both = render_graph(&spec(&[0, 1])).unwrap();
        assert_eq!(both.len(), a.len());
        assert!(a.iter().zip(&b).any(|(x, y)| (x[0] - y[0]).abs() > 1e-3));
        for ((x, y), z) in a.iter().zip(&b).zip(&both) {
            assert!((x[0] + y[0] - z[0]).abs() < 1e-6 && (x[1] + y[1] - z[1]).abs() < 1e-6);
        }
    }
}
