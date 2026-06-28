# Tutorial 2: Enhance Your Existing Agent (BYOA)

Wrap your existing Python agent objects with AgentFabric infrastructure without rewriting code.

```python
from agent_fabric.adapters.generic import GenericAgentAdapter

adapter = GenericAgentAdapter(agent_instance=my_existing_agent, run_method_name="execute")
res = adapter.run("Run task")
```
