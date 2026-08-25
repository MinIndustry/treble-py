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
    filter.set_parameter("sample_rate", sample_rate);
    for (name, value) in &spec.params {
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
}
