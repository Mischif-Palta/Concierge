import json
import random
from pathlib import Path


SEED = 42
BASELINE_SESSIONS = 20
AGENT_SESSIONS = 20


def generate_baseline_session(rng):
    products = rng.randint(1, 2)
    average_item_price = rng.uniform(400, 1200)

    return round(products * average_item_price, 2)


def generate_agent_session(rng):
    products = rng.randint(1, 3)
    average_item_price = rng.uniform(700, 1800)

    return round(products * average_item_price, 2)


def main():
    rng = random.Random(SEED)

    baseline = [
        generate_baseline_session(rng)
        for _ in range(BASELINE_SESSIONS)
    ]

    agent_assisted = [
        generate_agent_session(rng)
        for _ in range(AGENT_SESSIONS)
    ]

    baseline_aov = round(
        sum(baseline) / len(baseline),
        2
    )

    agent_aov = round(
        sum(agent_assisted) / len(agent_assisted),
        2
    )

    lift_percentage = round(
        ((agent_aov - baseline_aov) / baseline_aov) * 100,
        2
    )

    result = {
        "simulation": True,
        "seed": SEED,
        "sessions": {
            "baseline": BASELINE_SESSIONS,
            "agent_assisted": AGENT_SESSIONS
        },
        "baseline": {
            "orders": baseline,
            "aov": baseline_aov
        },
        "agent_assisted": {
            "orders": agent_assisted,
            "aov": agent_aov
        },
        "aov_lift_percentage": lift_percentage
    }

    output_path = Path(__file__).parent / "revenue_results.json"

    output_path.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8"
    )

    print("=" * 52)
    print("CONCIERGE REVENUE SIMULATION")
    print("=" * 52)

    print("\n⚠ SYNTHETIC SIMULATION")
    print("This is simulated data, not production revenue.")

    print(f"\nSeed: {SEED}")
    print(f"Baseline sessions: {BASELINE_SESSIONS}")
    print(f"Agent-assisted sessions: {AGENT_SESSIONS}")

    print("\nBaseline AOV")
    print(f"    ₹{baseline_aov}")

    print("\nAgent-assisted AOV")
    print(f"    ₹{agent_aov}")

    print("\nAOV Lift")
    print(f"    {lift_percentage}%")

    print(f"\n✓ Results saved to:")
    print(f"    {output_path}")


if __name__ == "__main__":
    main()