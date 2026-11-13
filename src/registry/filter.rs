use treble::core::graph::Filter;
use treble_meta::Parameter;

use crate::spec::FilterSpec;

pub fn build_filter(spec: &FilterSpec, sample_rate: f32) -> Result<Box<dyn Filter>, String> {
    let registration = inventory::iter::<treble::meta::FilterRegistration>()
        .find(|entry| (entry.info)().type_id == spec.filter_type)
        .ok_or_else(|| format!("Unknown filter type: '{}'", spec.filter_type))?;
    let info = (registration.info)();

    let parameter_name = |parameter: &Parameter<&'static str>| match parameter {
        Parameter::Toggle { field_name, .. }
        | Parameter::Range { field_name, .. }
        | Parameter::Float { field_name, .. }
        | Parameter::Int { field_name, .. }
        | Parameter::List { field_name, .. } => *field_name,
    };
    // Engine-owned parameters (`access = engine` in the filter metadata, e.g.
    // `sample_rate`) are injected below from the render rate. A value carried
    // by the spec is ignored: letting it through detunes rate-dependent filters.
    let engine_owned = treble::meta::engine_owned_params(&spec.filter_type);
    let known_parameters: Vec<&str> = info
        .inputs
        .iter()
        .filter_map(|input| input.parameter.as_ref())
        .map(parameter_name)
        .collect();

    for (name, value) in &spec.params {
        if !known_parameters.contains(&name.as_str()) {
            return Err(format!(
                "Unknown parameter '{name}' for filter '{}'",
                spec.filter_type
            ));
        }
        if !value.is_number() {
            return Err(format!(
                "Parameter '{name}' for filter '{}' must be numeric",
                spec.filter_type
            ));
        }
    }

    let mut filter = (registration.create)();
    if filter.supports_parameter("sample_rate") {
        filter.set_parameter("sample_rate", sample_rate);
    }
    for (name, value) in &spec.params {
        if engine_owned.contains(&name.as_str()) {
            continue;
        }
        filter.set_parameter(name, value.as_f64().unwrap() as f32);
    }
    Ok(filter)
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;

    use super::*;

    #[test]
    fn inventory_builds_registered_filter() {
        let spec = FilterSpec {
            filter_type: "GainFilter".into(),
            params: HashMap::from([("factor".into(), serde_json::json!(0.5))]),
        };
        assert!(build_filter(&spec, 44_100.0).is_ok());
    }

    #[test]
    fn unknown_parameter_is_rejected() {
        let spec = FilterSpec {
            filter_type: "GainFilter".into(),
            params: HashMap::from([("facotr".into(), serde_json::json!(0.5))]),
        };
        assert!(build_filter(&spec, 44_100.0).is_err());
    }

    #[test]
    fn spec_cannot_override_engine_owned_sample_rate() {
        use crate::spec::GraphSpec;
        let render = |params: serde_json::Value| {
            let spec: GraphSpec = serde_json::from_value(serde_json::json!({
                "note": 60, "note_on": 0.0, "note_off": 0.3, "duration": 0.5,
                "sources": [{"sources": [{"waveform": "saw", "envelope": {
                    "attack": [0.01, 1.0, 0.0, 0.0], "decay": [0.1, 0.8, 0.0, 1.0],
                    "sustain": 0.8, "release": [0.1, 0.0, 0.0, 0.0]}}],
                    "base_frequency": 440.0, "mix_mode": "Average",
                    "glob_ampl": {"attack": [0.01, 1.0, 0.0, 0.0], "decay": [0.1, 0.8, 0.0, 1.0],
                        "sustain": 0.8, "release": [0.1, 0.0, 0.0, 0.0]}}],
                "filters": [{"type": "LowPassFilter", "params": params}],
                "connections": [{"SourceFilter": {"source": 0, "filter": 0}},
                                {"FilterSink": {"filter": 0, "sink": 0}}],
            }))
            .unwrap();
            crate::renderer::render_graph(&spec).unwrap()
        };
        let base = render(serde_json::json!({"cutoff_frequency": 800.0}));
        let stale = render(serde_json::json!({"cutoff_frequency": 800.0, "sample_rate": 8000.0}));
        assert_eq!(base, stale);
    }
}
