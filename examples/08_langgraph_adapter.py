"""
08_langgraph_adapter.py — LangGraph framework adapter example.
"""
from agent_fabric.adapters.langgraph_adapter import LangGraphAdapter

class MockLangGraphApp:
    def invoke(self, input_dict: dict) -> dict:
        return {"messages": ["LangGraph graph executed successfully."]}

def main():
    app = MockLangGraphApp()
    adapter = LangGraphAdapter(graph_app=app)
    res = adapter.run("Execute workflow graph")
    print("LangGraph Adapter Result:", res.text)

if __name__ == "__main__":
    main()
