use rustic::core::envelope::prelude::{ADSREnvelopeBuilder, BezierSegment, ConstantSegment};
use rustic::core::generator::prelude::SingleToneGenerator;
use rustic::core::generator::prelude::{
    Waveform,
    builder::{MultiToneGeneratorBuilder, ToneGeneratorBuilder},
};
use rustic::core::graph::{MonophonicAllocationStrategy, MonophonicSource, Source};

use super::frequency::build_frequency_relation;
use crate::spec::{MultiSourceSpec, SourceSpec};

pub fn build_single_source(spec: &SourceSpec) -> SingleToneGenerator {
    let waveform = Waveform::from(spec.waveform.as_str());
    let freq_relation = build_frequency_relation(&spec.frequency_relation);

    let glob_ampl_adsr = ADSREnvelopeBuilder::new()
        .attack(Box::new(BezierSegment::new(
            0.0,
            spec.envelope.attack.1,
            spec.envelope.attack.0,
            (spec.envelope.attack.2, spec.envelope.attack.3),
        )))
        .decay(Box::new(BezierSegment::new(
            spec.envelope.attack.1,
            spec.envelope.decay.0,
            spec.envelope.decay.1,
            (spec.envelope.decay.2, spec.envelope.decay.3),
        )))
        .sustain(Box::new(ConstantSegment::new(spec.envelope.sustain, None)))
        .release(Box::new(BezierSegment::new(
            spec.envelope.sustain,
            spec.envelope.release.1,
            spec.envelope.release.0,
            (spec.envelope.release.2, spec.envelope.release.3),
        )))
        .build();

    ToneGeneratorBuilder::new()
        .waveform(waveform)
        .frequency_relation(freq_relation)
        .amplitude_envelope(Box::new(glob_ampl_adsr))
        .build()
}

pub fn build_source(spec: &MultiSourceSpec, sample_rate: f32) -> Box<dyn Source> {
    let glob_ampl_adsr = ADSREnvelopeBuilder::new()
        .attack(Box::new(BezierSegment::new(
            0.0,
            spec.glob_ampl.attack.1,
            spec.glob_ampl.attack.0,
            (spec.glob_ampl.attack.2, spec.glob_ampl.attack.3),
        )))
        .decay(Box::new(BezierSegment::new(
            spec.glob_ampl.attack.1,
            spec.glob_ampl.decay.0,
            spec.glob_ampl.decay.1,
            (spec.glob_ampl.decay.2, spec.glob_ampl.decay.3),
        )))
        .sustain(Box::new(ConstantSegment::new(spec.glob_ampl.sustain, None)))
        .release(Box::new(BezierSegment::new(
            spec.glob_ampl.sustain,
            spec.glob_ampl.release.1,
            spec.glob_ampl.release.0,
            (spec.glob_ampl.release.2, spec.glob_ampl.release.3),
        )))
        .build();

    let mut builder = MultiToneGeneratorBuilder::new();
    for source in spec.sources.iter().map(|s| build_single_source(s)) {
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
