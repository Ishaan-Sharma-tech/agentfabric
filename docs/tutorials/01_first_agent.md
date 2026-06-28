# Tutorial 1: First Agent in 60 Seconds

Learn how to initialize and execute your first AgentFabric agent in 3 lines of code.

```python
from agent_fabric import Agent

agent = Agent("researcher")
result = agent.run("Hello AgentFabric!")
print(result.text)
```
