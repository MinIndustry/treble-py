use std::collections::HashMap;

use rustic::core::generator::prelude::FrequencyRelation;

use crate::spec::FrequencyRelationSpec;

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
