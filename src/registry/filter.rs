use rustic::core::filters::prelude::*;
use rustic::core::graph::Filter;
use rustic_meta::MetaFilter;

use super::helpers::{get_f32, get_usize};
use crate::spec::FilterSpec;

pub fn build_filter(spec: &FilterSpec, sample_rate: f32) -> Result<Box<dyn Filter>, String> {
    let p = &spec.params;
    let filter: Box<dyn Filter> = match spec.filter_type.as_str() {
        "LowPassFilter" => Box::new(LowPassFilter::new(
            get_f32(p, "cutoff_frequency", 1000.0),
            sample_rate,
        )),
        "HighPassFilter" => Box::new(HighPassFilter::new(
            get_f32(p, "cutoff_frequency", 1000.0),
            sample_rate,
        )),
        "BandPass" => Box::new(BandPass::new(
            get_f32(p, "low", 200.0),
            get_f32(p, "high", 4000.0),
            sample_rate,
        )),
        "ResonantBandpassFilter" => Box::new(ResonantBandpassFilter::new(
            get_f32(p, "center", 1000.0),
            get_f32(p, "quality", 1.0),
            sample_rate,
        )),
        "MovingAverage" => Box::new(MovingAverage::new(get_usize(p, "size", 5))),
        "GainFilter" => Box::new(GainFilter::new(get_f32(p, "factor", 1.0))),
        "Clipper" => Box::new(Clipper::new(get_f32(p, "max_ampl", 0.8))),
        "Compressor" => {
            let mut c = Compressor::default();
            for (k, v) in p {
                if let Some(f) = v.as_f64() {
                    c.set_parameter(k.as_str(), f as f32);
                }
            }
            Box::new(c)
        }
        "Tremolo" => Box::new(Tremolo::new(
            get_f32(p, "frequency", 5.0),
            get_f32(p, "depth", 0.5),
            sample_rate,
        )),
        "DelayFilter" => Box::new(DelayFilter::new(sample_rate, get_f32(p, "delay_for", 0.5))),
        "PanFilter" => Box::new(PanFilter::new(get_f32(p, "direction", 0.0))),
        other => return Err(format!("Unknown filter type: '{other}'")),
    };
    Ok(filter)
}
