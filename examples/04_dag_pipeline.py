"""
04_dag_pipeline.py — Workflow DAG pipeline execution.
"""
import asyncio
from agent_fabric.pipelines.dag import Pipeline, PipelineNode, PipelineEdge
from agent_fabric.pipelines.executor import PipelineExecutor

async def main():
    pipe = Pipeline(
        id="sample-pipeline",
        name="Data Pipeline",
        nodes=[
            PipelineNode(id="fetch", type="transform", config={"template": "Fetched Data"}),
            PipelineNode(id="summarize", type="transform", depends_on=["fetch"], config={"template": "Summary of ${fetch.output}"})
        ],
        edges=[]
    )
    executor = PipelineExecutor(pipe)
    run_rec = await executor.run()
    print("Pipeline Output Results:", run_rec.outputs)

if __name__ == "__main__":
    asyncio.run(main())
