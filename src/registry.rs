use std::collections::HashMap;

use rustic::core::envelope::prelude::{ADSREnvelopeBuilder, ConstantSegment, LinearSegment};
use rustic::core::filters::prelude::*;
use rustic::core::generator::prelude::{
    FrequencyRelation, MixMode, Waveform,
    builder::{MultiToneGeneratorBuilder, ToneGeneratorBuilder},
};
use rustic::core::graph::{Filter, MonophonicAllocationStrategy, MonophonicSource, Source};
use rustic_meta::MetaFilter;

use crate::spec::{FilterSpec, FrequencyRelationSpec, SourceSpec};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

pub fn get_f32(params: &HashMap<String, serde_json::Value>, key: &str, default: f32) -> f32 {
    params
        .get(key)
        .and_then(|v| v.as_f64())
        .map(|v| v as f32)
        .unwrap_or(default)
}

pub fn get_usize(params: &HashMap<String, serde_json::Value>, key: &str, default: usize) -> usize {
    params
        .get(key)
        .and_then(|v| v.as_u64())
        .map(|v| v as usize)
        .unwrap_or(default)
}

// ---------------------------------------------------------------------------
// FrequencyRelation
// ---------------------------------------------------------------------------

pub fn build_frequency_relation(spec: &FrequencyRelationSpec) -> FrequencyRelation {
    match spec {
        FrequencyRelationSpec::Identity => FrequencyRelation::Identity,
        FrequencyRelationSpec::Tagged(s) => parse_relation_string(s),
        FrequencyRelationSpec::Object(map) => parse_relation_object(map),
    }
}

fn parse_relation_string(s: &str) -> FrequencyRelation {
    if s == "identity" {
        return FrequencyRelation::Identity;
    }
    if let Some(rest) = s.strip_prefix("harmonic:") {
        if let Ok(n) = rest.parse::<u8>() {
            return FrequencyRelation::Harmonic(n);
        }
    }
    if let Some(rest) = s.strip_prefix("ratio:") {
        if let Ok(f) = rest.parse::<f32>() {
            return FrequencyRelation::Ratio(f);
        }
    }
    if let Some(rest) = s.strip_prefix("semitones:") {
        if let Ok(i) = rest.parse::<i32>() {
            return FrequencyRelation::Semitones(i);
        }
    }
    if let Some(rest) = s.strip_prefix("offset:") {
        if let Ok(f) = rest.parse::<f32>() {
            return FrequencyRelation::Offset(f);
        }
    }
    FrequencyRelation::Identity
}

fn parse_relation_object(map: &HashMap<String, serde_json::Value>) -> FrequencyRelation {
    if let Some(v) = map.get("harmonic").and_then(|v| v.as_u64()) {
        FrequencyRelation::Harmonic(v as u8)
    } else if let Some(v) = map.get("ratio").and_then(|v| v.as_f64()) {
        FrequencyRelation::Ratio(v as f32)
    } else if let Some(v) = map.get("semitones").and_then(|v| v.as_i64()) {
        FrequencyRelation::Semitones(v as i32)
    } else if let Some(v) = map.get("offset").and_then(|v| v.as_f64()) {
        FrequencyRelation::Offset(v as f32)
    } else if let Some(v) = map.get("constant").and_then(|v| v.as_f64()) {
        FrequencyRelation::Constant(v as f32)
    } else {
        FrequencyRelation::Identity
    }
}

// ---------------------------------------------------------------------------
// Source
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Filter
// ---------------------------------------------------------------------------

pub fn build_filter(spec: &FilterSpec, sample_rate: f32) -> Result<Box<dyn Filter>, String> {
    let p = &spec.params;
    let filter: Box<dyn Filter> = match spec.filter_type.as_str() {
        "lowpass" => Box::new(LowPassFilter::new(
            get_f32(p, "cutoff_frequency", 1000.0),
            sample_rate,
        )),
        "highpass" => Box::new(HighPassFilter::new(
            get_f32(p, "cutoff_frequency", 1000.0),
            sample_rate,
        )),
        "bandpass" => Box::new(BandPass::new(
            get_f32(p, "low", 200.0),
            get_f32(p, "high", 4000.0),
            sample_rate,
        )),
        "resonant_bandpass" => Box::new(ResonantBandpassFilter::new(
            get_f32(p, "center", 1000.0),
            get_f32(p, "quality", 1.0),
            sample_rate,
        )),
        "moving_average" => Box::new(MovingAverage::new(get_usize(p, "size", 5))),
        "gain" => Box::new(GainFilter::new(get_f32(p, "factor", 1.0))),
        "clipper" => Box::new(Clipper::new(get_f32(p, "max_ampl", 0.8))),
        "compressor" => {
            let mut c = Compressor::default();
            for (k, v) in p {
                if let Some(f) = v.as_f64() {
                    c.set_parameter(k.as_str(), f as f32);
                }
            }
            Box::new(c)
        }
        "tremolo" => Box::new(Tremolo::new(
            get_f32(p, "frequency", 5.0),
            get_f32(p, "depth", 0.5),
            sample_rate,
        )),
        "delay" => Box::new(DelayFilter::new(sample_rate, get_f32(p, "delay_for", 0.5))),
        "pan" => Box::new(PanFilter::new(get_f32(p, "direction", 0.0))),
        other => return Err(format!("Unknown filter type: '{other}'")),
    };
    Ok(filter)
}
