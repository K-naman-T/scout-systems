#!/usr/bin/env python3
"""OSS Scout v2 — FDE-targeted: finds issues in tools companies deploy in customer environments."""

import subprocess, json, os, sys, time
from pathlib import Path

HOME = Path(os.environ.get("HOME", "/root"))
OUT_DIR = HOME / "scout-systems/oss-scout/output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

date_tag = os.popen("date +%Y-%m-%d").read().strip()
out_file = OUT_DIR / f"oss-digest-fde-{date_tag}.md"

# Categories that signal FDE capability
CATEGORIES = {
    "Inference Serving": [
        "vllm-project/vllm",
        "huggingface/text-generation-inference",
        "triton-inference-server/server",
        "bentoml/BentoML",
        "ray-project/ray",
        "mozilla-iot/tts",
        "olive-ai/olive",
    ],
    "Edge / On-Prem Deployment": [
        "kubeedge/kubeedge",
        "openyurtio/openyurt",
        "k3s-io/k3s",
        "eclipse-iofog/iofog",
        "edgexfoundry/edgex-go",
        "nvidia/ai-workbench",
        "ubuntu/microk8s",
    ],
    "Data Integration & Pipelines": [
        "airbytehq/airbyte",
        "dagster-io/dagster",
        "PrefectHQ/prefect",
        "dbt-labs/dbt-core",
        "meltano/meltano",
        "apache/airflow",
        "temporalio/temporal",
    ],
    "Infra & Deployment Tooling": [
        "crossplane/crossplane",
        "argoproj/argo-cd",
        "argoproj/argo-workflows",
        "hashicorp/terraform",
        "kubernetes-sigs/external-dns",
        "external-secrets/external-secrets",
        "cert-manager/cert-manager",
        "helm/helm",
    ],
    "AI Engineering & Agents": [
        "langchain-ai/langchain",
        "run-llama/llama_index",
        "microsoft/autogen",
        "crewAIInc/crewAI",
        "chatchat-space/Langchain-Chatchat",
        "weaviate/weaviate",
        "qdrant/qdrant",
        "chroma-core/chroma",
    ],
    "GPU / HPC / Edge ML": [
        "NVIDIA/TensorRT",
        "NVIDIA/TensorRT-LLM",
        "pytorch/pytorch",
        "openai/triton",
        "onnx/onnx",
        "NVIDIA/NeMo",
        "NVIDIA/cuda-python",
    ],
    "Industrial IoT & Scientific": [
        "eclipse-milo/milo",
        "apache/plc4x",
        "eclipse-zenoh/zenoh",
        "dask/dask",
        "rapidsai/cudf",
        "pyvista/pyvista",
    ],
}

labels = ["good first issue", "help wanted", "bug", "enhancement"]
max_per_label = 5

with open(out_file, "w") as f:
    f.write(f"# FDE-Targeted OSS Scout Digest — {date_tag}\n\n")
    f.write(f"Focus: tools deployed in customer environments (inference, edge, data pipelines, infra)\n\n")

    total = 0
    for category, repos in CATEGORIES.items():
        f.write(f"## {category}\n\n")
        cat_total = 0
        seen = set()
        for repo in repos:
            for label in labels:
                r = subprocess.run(
                    ["gh", "search", "issues",
                     "--repo", repo,
                     "--label", label,
                     "--state", "open",
                     "--limit", str(max_per_label),
                     "--json", "title,url,number,labels,updatedAt,state"],
                    capture_output=True, text=True, timeout=15
                )
                if r.returncode != 0 or not r.stdout.strip():
                    continue
                try:
                    items = json.loads(r.stdout)
                except json.JSONDecodeError:
                    continue
                if not items:
                    continue

                for i in items:
                    if i["url"] in seen:
                        continue
                    seen.add(i["url"])
                    labels_str = ", ".join([l["name"] for l in i.get("labels", [])])
                    f.write(f"- [{i['title']}]({i['url']}) `{repo}` [{labels_str}]\n")
                    cat_total += 1
                    total += 1

                time.sleep(2.5)  # rate limit — GitHub search: 30 queries/min authed

            # If we already have enough from this repo, skip remaining labels
            if cat_total >= 15:
                break

        if cat_total == 0:
            f.write("  _(no open issues found)_\n")
        f.write("\n")

    f.write(f"---\n**Total: {total} FDE-relevant issues found**\n")

print(f"Digest written to {out_file}")
print(f"Total: {total} issues")
