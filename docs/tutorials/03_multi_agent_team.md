# Tutorial 3: Multi-Agent Teams

Orchestrate teams using sequential, parallel, or supervisor strategies.

```python
from agent_fabric.runtime.team import Team
from agent_fabric.runtime.agent import Agent

team = Team(agents=[Agent("researcher"), Agent("writer")], strategy="supervisor")
```
