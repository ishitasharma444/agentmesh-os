#%%
from dotenv import load_dotenv
load_dotenv()
from crewai import LLM,Agent,Task,Crew
llm2=LLM(
    model="gemini/gemini-2.5-flash",
    temperature=0.5
)
transport_agent=Agent(
    role="Transportation Optimization and Resource Allocation Agent,",
    goal="Analyze shipment characteristics and operational conditions to determine the most efficient, cost-effective, safe, and environmentally responsible transportation strategy while ensuring timely delivery and optimal resource utilization.",
    backstory="""The Transportation Optimization Agent serves as the execution planning layer within the AgentMesh ecosystem. Modern logistics operations require more than simply selecting a route or assigning a vehicle. Every shipment has unique characteristics including weight, volume, quantity, urgency, handling requirements, and demand conditions.

The Transportation Optimization Agent evaluates shipment attributes, available transportation modes, operational constraints, fuel consumption patterns, safety considerations, delivery requirements, and resource availability to determine the most suitable transportation strategy.

The agent continuously balances multiple objectives including delivery speed, transportation safety, fuel efficiency, operational cost, resource utilization, and environmental impact. It collaborates with Logistics, Finance, and Risk Agents to ensure that every shipment is transported using the most appropriate mode while maintaining organizational efficiency and reliability.

Its objective is to optimize transportation decisions by intelligently matching shipment requirements with available transportation resources and operational conditions.""",
    verbose=    False,
    llm=llm2
)
trans_task=Task(
    description="Evaluate shipment requirements and operational conditions to identify the optimal transportation strategy. Analyze cargo weight, volume, quantity, urgency, demand patterns, safety requirements, fuel efficiency, and resource availability to recommend the most efficient and sustainable transportation solution.",
    agent=transport_agent,
    expected_output="""Transportation Optimization Report

                        1. Recommended Transportation Mode
                        2. Recommended Vehicle Type
                        3. Capacity Utilization Analysis
                        4. Fuel Efficiency Assessment
                        5. Safety Assessment
                        6. Cost Efficiency Analysis
                        7. Resource Allocation Plan
                        8. Environmental Impact Assessment
                        9. Confidence Score
                        10. Final Transportation Recommendation""",
    verbose=False
)


import asyncio

async def main():
    crew = Crew(
        agents=[transport_agent],
        tasks=[trans_task],
        verbose=False
    )
    result = await crew.kickoff_async()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())