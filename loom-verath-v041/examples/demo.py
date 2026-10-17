from pathlib import Path

from loom_verath import LoomVerathRuntime


data_dir = Path(__file__).parent / ".demo-runtime"

with LoomVerathRuntime(data_dir) as runtime:
    result = runtime.run(
        "Create a fireball with VOX radius 4 duration 3 intensity 0.7",
        requested_mode="simulation",
    )
    print(result.to_dict())
    print(runtime.replay(result.session_id))
    print(runtime.verify())

