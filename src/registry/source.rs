use rustic::core::envelope::prelude::{ADSREnvelopeBuilder, ConstantSegment, LinearSegment};
use rustic::core::generator::prelude::{
    MixMode, Waveform,
    builder::{MultiToneGeneratorBuilder, ToneGeneratorBuilder},
};
use rustic::core::graph::{MonophonicAllocationStrategy, MonophonicSource, Source};

use super::frequency::build_frequency_relation;
use crate::spec::SourceSpec;

pub fn build_source(spec: &SourceSpec, sample_rate: f32) -> Box<dyn Source> {
    let waveform = Waveform::from(spec.waveform.as_str());
    let freq_relation = build_frequency_relation(&spec.frequency_relation);

    let adsr = ADSREnvelopeBuilder::new()
        .attack(Box::new(LinearSegment::new(0.0, 1.0, spec.attack)))
        .decay(Box::new(LinearSegment::new(1.0, spec.sustain, spec.decay)))
        .sustain(Box::new(ConstantSegment::new(spec.sustain, None)))
        .release(Box::new(LinearSegment::new(
            spec.sustain,
            0.0,
            spec.release,
        )))
        .build();

    let tone = ToneGeneratorBuilder::new()
        .waveform(waveform)
        .frequency_relation(freq_relation)
        .amplitude_envelope(Box::new(adsr))
        .build();

    let multi = MultiToneGeneratorBuilder::new()
        .add_generator(tone)
        .mix_mode(MixMode::Sum)
        .build();

    Box::new(MonophonicSource::new(
        multi,
        sample_rate,
        MonophonicAllocationStrategy::Replace,
    ))
}
