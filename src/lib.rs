mod registry;
#[path = "render.rs"]
mod renderer;
mod spec;

use numpy::{IntoPyArray, PyArray2};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyList};
use pythonize::depythonize;
use rayon::prelude::*;

use spec::GraphSpec;

/// Convert rendered stereo frames into a (N, 2) float32 numpy array.
fn frames_to_array<'py>(
    py: Python<'py>,
    frames: Vec<[f32; 2]>,
) -> PyResult<Bound<'py, PyArray2<f32>>> {
    let n = frames.len();
    let flat: Vec<f32> = frames.into_iter().flat_map(|f| f.into_iter()).collect();
    let array = numpy::ndarray::Array2::from_shape_vec((n, 2), flat)
        .map_err(|e| PyValueError::new_err(format!("Array shape error: {e}")))?;
    Ok(array.into_pyarray(py))
}

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
/// ```py
/// import treble_py
/// import soundfile as sf
///
/// audio = treble_py.render({
///     "note": 60, "note_on": 0.0, "note_off": 0.5, "duration": 0.7,
///     "sources": [{"sources": [{"waveform": "sine"}], "base_frequency": 440.0}],
///     "filters": [{"type": "LowPassFilter", "params": {"cutoff_frequency": 2000.0}}],
///     "connections": [{"SourceFilter": {"source": 0, "filter": 0}},
///                     {"FilterSink": {"filter": 0, "sink": 0}}],
/// })
/// # audio.shape == (N, 2), dtype float32
/// sf.write("out.wav", audio, samplerate=44100)
/// ```
#[pyfunction]
fn render<'py>(
    py: Python<'py>,
    spec_dict: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyArray2<f32>>> {
    let spec: GraphSpec =
        depythonize(spec_dict).map_err(|e| PyValueError::new_err(format!("Invalid spec: {e}")))?;

    let frames = py
        .detach(|| renderer::render_graph(&spec))
        .map_err(PyValueError::new_err)?;

    frames_to_array(py, frames)
}

/// Render many synthesis graph specs in parallel.
///
/// The GIL is released and specs are rendered across a rayon thread pool,
/// so wall-clock time scales with available cores. Order is preserved.
///
/// Args:
///     spec_dicts: list of GraphSpec dicts (same format as ``render``).
///
/// Returns:
///     list of numpy.ndarray, each of shape (N_samples, 2), dtype float32.
///
/// Example::
///
/// ```py
/// import treble_py
///
/// audios = treble_py.render_batch([spec_a, spec_b, spec_c])
/// ```
#[pyfunction]
fn render_batch<'py>(
    py: Python<'py>,
    spec_dicts: &Bound<'py, PyList>,
) -> PyResult<Vec<Bound<'py, PyArray2<f32>>>> {
    let specs: Vec<GraphSpec> = spec_dicts
        .iter()
        .enumerate()
        .map(|(i, item)| {
            depythonize(&item)
                .map_err(|e| PyValueError::new_err(format!("Invalid spec at index {i}: {e}")))
        })
        .collect::<PyResult<_>>()?;

    let rendered: Vec<Result<Vec<[f32; 2]>, String>> = py.detach(|| {
        specs
            .par_iter()
            .map(renderer::render_graph)
            .collect()
    });

    rendered
        .into_iter()
        .enumerate()
        .map(|(i, result)| {
            let frames = result
                .map_err(|e| PyValueError::new_err(format!("Render failed at index {i}: {e}")))?;
            frames_to_array(py, frames)
        })
        .collect()
}

/// Returns metadata for all registered filter types.
///
/// Returns:
///     list of dicts, each with keys: name, description, inputs, outputs.
///
/// Example::
///
/// ```py
/// import treble_py
///
/// for f in treble_py.available_filters():
///     print(f["name"], "-", f["description"])
/// # lowpass - A simple lowpass filter
/// # highpass - A simple highpass filter
/// # ...
/// ```
#[pyfunction]
fn available_filters(py: Python<'_>) -> PyResult<Py<PyAny>> {
    let filters = treble::meta::get_filters();
    let obj = pythonize::pythonize(py, &filters)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(obj.unbind())
}

/// Returns metadata for all available source (generator/waveform) types.
///
/// Returns:
///     list of dicts, each with keys: name, type_id, description, parameters, output_count.
///
/// Example::
///
/// ```py
/// import treble_py
///
/// for s in treble_py.available_sources():
///     params = [p["name"] for p in s["parameters"]]
///     print(f'{s["name"]}: {", ".join(params)}')
/// # sine: attack, decay, sustain, release
/// # square: attack, decay, sustain, release
/// # ...
/// ```
#[pyfunction]
fn available_sources(py: Python<'_>) -> PyResult<Py<PyAny>> {
    let generators = treble::meta::get_generators();
    let obj = pythonize::pythonize(py, &generators)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(obj.unbind())
}

#[pymodule]
fn treble_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(render, m)?)?;
    m.add_function(wrap_pyfunction!(render_batch, m)?)?;
    m.add_function(wrap_pyfunction!(available_filters, m)?)?;
    m.add_function(wrap_pyfunction!(available_sources, m)?)?;
    Ok(())
}
