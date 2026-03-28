from typing import Callable
from rustic_py import SourceSpec, GraphSpec, MultiSourceSpec, ADSRSpec
from rustic_py import ResonantBandpassFilter, LowPassFilter
import rustic_py
from rustic_py.rustic_py import render

all_filters = rustic_py.rustic_py.available_filters()

def find_longest(key, filters, base=0) -> int:
    longest: int = base
    for fil in filters:
        if callable(key):
            cur_len: int = len(key(fil))
        else:
            cur_len: int = len(fil.get(key, ""))
        if cur_len > longest:
            longest = cur_len

    return longest


def _print_filter(filter_spec, columns, paddings: list, short=True):
    for i, column in enumerate(columns):
        if callable(column[1]):
            print(column[1](filter_spec).ljust(paddings[i]), end="|")
        else:
            print(filter_spec[column[1]].ljust(paddings[i]), end="|")
    print()


def print_filter_table(filters):
    columns = [
        ("Name", "name"),
        ("Type", "type_id"),
        ("Inputs", lambda f: (
            ", ".join([i["label"] for i in filter(lambda fil: fil["label"] is not None, f["inputs"])])
            )
        )
    ]

    paddings = [
        find_longest(x[1], filters, base=len(x[0])) for x in columns
    ]

    for i, column in enumerate(columns):
        print(column[0].ljust(paddings[i]), end="|")
    print()

    for fil in filters:
        _print_filter(fil, columns, paddings)

print_filter_table(all_filters)

source = MultiSourceSpec(
        sources=[
            SourceSpec(
                waveform="sine",
                frequency_relation="identity",
                envelope=ADSRSpec(
                    attack=(0.5, 1.0, 0.5, 0.0),
                    decay=(0.2, 0.8, 0.0, 0.0),
                    sustain=0.8,
                    release=(2.0, 0.0, 2.0, 0.8)
            )),
            SourceSpec(
                waveform="saw",
                frequency_relation="identity"
            )
        ],
        mix_mode="Sum")

graph = GraphSpec(
    note_on=0.2,
    note_off=1.6,
    duration=2.2,
    note=20,
    source=source,
    filters=[
        LowPassFilter(),
        ResonantBandpassFilter()
    ],
    connections = [
        
    ]
)


print("====== SPEC =====")
print(graph.to_spec())

print("==== END SPEC ===")
rendered = render(graph.to_spec())

import matplotlib.pyplot as plt

plt.plot(rendered)
plt.show()
