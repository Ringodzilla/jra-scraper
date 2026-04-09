import subprocess
from pathlib import Path


def test_init_multi_agent_experiment_creates_templates(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    exp_id = "test_multi_agent_init"
    exp_dir = root / "experiments" / exp_id

    if exp_dir.exists():
        for f in exp_dir.glob("*"):
            f.unlink()
        exp_dir.rmdir()

    subprocess.run(
        ["bash", str(root / "scripts/init_multi_agent_experiment.sh"), exp_id],
        check=True,
        cwd=root,
    )

    assert (exp_dir / "01_data_collector.json").exists()
    assert (exp_dir / "02_analyzer.json").exists()
    assert (exp_dir / "03_simulator.json").exists()
    assert (exp_dir / "04_ev_calculator.json").exists()
    assert (exp_dir / "05_bet_builder.json").exists()
    assert (exp_dir / "06_reviewer.json").exists()
    assert (exp_dir / "OWNERSHIP.lock").exists()

    for f in exp_dir.glob("*"):
        f.unlink()
    exp_dir.rmdir()
