"""
05_cron_scheduler.py — Cron scheduler example.
"""
import asyncio
from agent_fabric.scheduler.scheduler import Schedule, SchedulerEngine

async def main():
    engine = SchedulerEngine()
    sched = Schedule(
        name="status_job",
        trigger_type="cron",
        trigger_config={"cron_expression": "*/5 * * * *"},
        target_type="agent",
        target_name="monitor_agent"
    )
    engine.create_schedule(sched)
    print("Created schedule job ID:", sched.id)

if __name__ == "__main__":
    asyncio.run(main())
