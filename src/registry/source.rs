use treble::core::envelope::prelude::{ADSREnvelopeBuilder, BezierSegment, ConstantSegment};
use treble::core::generator::prelude::SingleToneGenerator;
use treble::core::generator::prelude::{
    Waveform,
    builder::{MultiToneGeneratorBuilder, ToneGeneratorBuilder},
};
use treble::core::graph::{MonophonicAllocationStrategy, MonophonicSource, Source};

use super::frequency::build_frequency_relation;
use crate::spec::{MultiSourceSpec, SourceSpec};

/// One envelope segment from a spec tuple `(duration, level, control_time,
/// control_level)`: a Bezier from `from` to `level` over `duration` seconds.
/// `control_time` is in seconds from the segment's start, as every spec
/// writer gives it; the engine wants it as a fraction of the segment.
fn segment(
    from: f32,
    (duration, level, control_time, control_level): (f32, f32, f32, f32),
) -> Box<BezierSegment> {
    let cx = if duration > 0.0 {
        (control_time / duration).clamp(0.0, 1.0)
    } else {
        0.5
    };
    Box::new(BezierSegment::new(
        from,
        level,
        duration,
        (cx, control_level),
    ))
}

pub fn build_single_source(spec: &SourceSpec) -> SingleToneGenerator {
    let waveform = Waveform::from(spec.waveform.as_str());
    let freq_relation = build_frequency_relation(&spec.frequency_relation);

    let glob_ampl_adsr = ADSREnvelopeBuilder::new()
        .attack(segment(0.0, spec.envelope.attack))
        .decay(segment(spec.envelope.attack.1, spec.envelope.decay))
        .sustain(Box::new(ConstantSegment::new(spec.envelope.sustain, None)))
        .release(segment(spec.envelope.sustain, spec.envelope.release))
        .build();

    ToneGeneratorBuilder::new()
        .waveform(waveform)
        .frequency_relation(freq_relation)
        .amplitude_envelope(Box::new(glob_ampl_adsr))
        .build()
}

pub fn build_source(spec: &MultiSourceSpec, sample_rate: f32) -> Box<dyn Source> {
    let glob_ampl_adsr = ADSREnvelopeBuilder::new()
        .attack(segment(0.0, spec.glob_ampl.attack))
        .decay(segment(spec.glob_ampl.attack.1, spec.glob_ampl.decay))
        .sustain(Box::new(ConstantSegment::new(spec.glob_ampl.sustain, None)))
        .release(segment(spec.glob_ampl.sustain, spec.glob_ampl.release))
        .build();

    let mut builder = MultiToneGeneratorBuilder::new();
    for source in spec.sources.iter().map(build_single_source) {
        builder = builder.add_generator(source)
    }

    let multi = builder
        .mix_mode(spec.mix_mode.clone())
        .amplitude_envelope(Some(Box::new(glob_ampl_adsr)))
        .frequency(spec.base_frequency)
        .build();

    Box::new(MonophonicSource::new(
        multi,
        sample_rate,
        MonophonicAllocationStrategy::Replace,
    ))
}
