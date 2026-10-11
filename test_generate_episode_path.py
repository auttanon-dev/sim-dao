import os

import generate_episode as GE


def test_model_with_slash_writes_flat_file(tmp_path):
    """ชื่อโมเดล hf.co/... มี "/" — ต้องได้ไฟล์ในโฟลเดอร์ out ตรง ๆ และเขียนได้จริง"""
    out = str(tmp_path / "episodes")
    path = GE.episode_path(out, 3, "หลินเฟิง", "hf.co/nectec/pathumma-thaillm-8b-think-3.0.0-GGUF-Q4_K_M")
    assert os.path.dirname(path) == out
    assert "/" not in os.path.basename(path) and ":" not in os.path.basename(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("x")
    assert os.path.isfile(path)


def test_model_tag_colon():
    assert GE.episode_path("o", 1, "a", "qwen2.5:7b").endswith("episode_1_a_qwen2-5-7b.md")
