mod registry;
#[path = "render.rs"]
mod renderer;
mod spec;

use numpy::{IntoPyArray, PyArray2};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use spec::GraphSpec;

/// Render a synthesis graph spec to stereo audio.
///
/// Args:
///     spec_dict: Python dict conforming to the GraphSpec format.
///
/// Returns:
///     numpy.ndarray of shape (N_samples, 2), dtype float32.
///
/// Example::
///
///     audio = rustic_py.render({
///         "note": 60, "note_on": 0.0, "note_off": 0.5, "duration": 0.7,
///         "source": {"waveform": "sine", "attack": 0.01, "decay": 0.1,
///                    "sustain": 0.8, "release": 0.2},
///         "filters": [{"type": "lowpass", "params": {"cutoff_frequency": 2000.0}}],
///     })
#[pyfunction]
fn render<'py>(
    py: Python<'py>,
    spec_dict: &Bound<'py, PyDict>,
) -> PyResult<Bound<'py, PyArray2<f32>>> {
    let json_module = PyModule::import(py, "json")?;
    let json_str: String = json_module.call_method1("dumps", (spec_dict,))?.extract()?;

    let spec: GraphSpec = serde_json::from_str(&json_str)
        .map_err(|e| PyValueError::new_err(format!("Invalid spec: {e}")))?;

    let frames = renderer::render_graph(&spec).map_err(PyValueError::new_err)?;

    let n = frames.len();
    let flat: Vec<f32> = frames.into_iter().flat_map(|f| f.into_iter()).collect();
    let array = numpy::ndarray::Array2::from_shape_vec((n, 2), flat)
        .map_err(|e| PyValueError::new_err(format!("Array shape error: {e}")))?;

    Ok(array.into_pyarray(py))
}

/// Returns metadata for all registered filter types.
///
/// Returns:
///     list of dicts, each with keys: name, description, inputs, outputs.
#[pyfunction]
fn available_filters(py: Python<'_>) -> PyResult<Py<PyAny>> {
    let filters = rustic::meta::get_filters();
    let json_str =
        serde_json::to_string(&filters).map_err(|e| PyValueError::new_err(e.to_string()))?;

    let json_module = PyModule::import(py, "json")?;
    let obj = json_module.call_method1("loads", (json_str,))?;
    Ok(obj.unbind())
}

/// Returns metadata for all available source (generator/waveform) types.
///
/// Returns:
///     list of dicts, each with keys: name, type_id, description, parameters, output_count.
#[pyfunction]
fn available_sources(py: Python<'_>) -> PyResult<Py<PyAny>> {
    let generators = rustic::meta::get_generators();
    let json_str =
        serde_json::to_string(&generators).map_err(|e| PyValueError::new_err(e.to_string()))?;

    let json_module = PyModule::import(py, "json")?;
    let obj = json_module.call_method1("loads", (json_str,))?;
    Ok(obj.unbind())
}

#[pymodule]
fn rustic_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(render, m)?)?;
    m.add_function(wrap_pyfunction!(available_filters, m)?)?;
    m.add_function(wrap_pyfunction!(available_sources, m)?)?;
    Ok(())
}
