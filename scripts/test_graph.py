from python.rustic_py._classes import ADSRSpec
from rustic_py import SourceSpec
from rustic_py import GraphSpec, MultiSourceSpec

source = MultiSourceSpec(
        sources=[
            SourceSpec(
                waveform="pinknoise",
                envelope=ADSRSpec(
                    attack=(0.5, 1.0, 0.5, 0.0),
                    decay=()
                ))], mix_mode="Sum")
graph = GraphSpec(note_on=0.2, note_off=0.6, duration=1.0, note=64, source=source)
