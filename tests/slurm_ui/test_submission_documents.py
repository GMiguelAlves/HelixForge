import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("slurm_submission", ROOT / "ui/slurm/submission.py")
submission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(submission)


def base_plan(workflow="rnaseq"):
    conditions = [("treated", 1), ("treated", 2), ("control", 1), ("control", 2)]
    rna = [{"dataset":"study", "sample_id":f"rna_{condition}_{rep}", "run_accession":f"RUN{index}",
            "fastq_1":f"/scratch/fastq/rna_{index}_R1.fastq.gz", "fastq_2":f"/scratch/fastq/rna_{index}_R2.fastq.gz",
            "condition":condition, "batch":"batch1", "replicate":str(rep)} for index, (condition, rep) in enumerate(conditions, 1)]
    chip = [{"sample_id":"input_1", "fastq_1":"/scratch/fastq/input_R1.fastq.gz", "fastq_2":"/scratch/fastq/input_R2.fastq.gz",
             "layout":"paired", "condition":"control", "batch":"batch1", "replicate":"1", "is_control":True, "mark_or_factor":"input", "control_id":""}]
    chip += [{"sample_id":f"chip_{condition}_{rep}", "fastq_1":f"/scratch/fastq/chip_{index}_R1.fastq.gz", "fastq_2":f"/scratch/fastq/chip_{index}_R2.fastq.gz",
              "layout":"paired", "condition":condition, "batch":"batch1", "replicate":str(rep), "is_control":False,
              "mark_or_factor":"H3K27ac", "control_id":"input_1"} for index, (condition, rep) in enumerate(conditions, 1)]
    return {"name":"Analysis 01", "workflow":workflow,
            "clone":{"mode":"existing", "path":"/home/researcher/HelixForge", "repository":"https://github.com/GMiguelAlves/HelixForge.git", "ref":""},
            "storage":{"project_root":"/home/researcher/projects/analysis-01", "launch":"/home/researcher/launch/analysis-01", "output":"/scratch/researcher/analysis-01/results", "work":"/scratch/researcher/analysis-01/work"},
            "runtime":{"profile":"slurm,apptainer", "partition":"general", "account":"", "memory":"4", "hours":"12"},
            "organism":{"name":"Example organism", "reference_id":"assembly_v1", "genome_fasta":"/scratch/reference/genome.fa",
                        "transcriptome_fasta":"/scratch/reference/transcripts.fa", "annotation":"/scratch/reference/annotation.gtf", "blacklist":""},
            "science":{"quantification":"salmon", "peak_type":"narrow", "effective_genome_size":"2913022398",
                       "consensus_method":"replicate_support", "idr":False},
            "rnaseq_samples":rna if workflow in ("rnaseq", "all") else [], "chipseq_samples":chip if workflow in ("chipseq", "all") else [],
            "statistics":{"variable":"condition", "covariates":["batch"], "formula":"~ batch + condition", "alpha":"0.05", "lfc_threshold":"1", "min_replicates":"2", "genes":["gene1"],
                          "contrasts":[{"numerator":"treated", "denominator":"control"}]},
            "integration":{"rna_manifest":"/scratch/rna/rnaseq_run_manifest.json" if workflow == "integrative" else "",
                           "chip_manifest":"/scratch/chip/chipseq_run_manifest.json" if workflow == "integrative" else "", "policy_mode":"templates", "policy_paths":{}}}


class DocumentGenerationTests(unittest.TestCase):
    def documents(self, workflow):
        generated = submission.generate_documents(base_plan(workflow))
        return generated, {item["relative_path"]:item["content"] for item in generated["documents"]}

    def test_rnaseq_documents_follow_native_contract(self):
        generated, docs = self.documents("rnaseq")
        self.assertEqual(set(docs), {"config/rnaseq_metadata.tsv", "config/rnaseq_user_settings.sh", "config/rnaseq_pipeline_config.sh", "specifications/de_spec.json", "run.config"})
        self.assertTrue(docs["config/rnaseq_metadata.tsv"].startswith("dataset\tsample_id\trun_accession\tfastq_1\tfastq_2"))
        spec = json.loads(docs["specifications/de_spec.json"])
        self.assertEqual(spec["design"]["formula"], "~ batch + condition")
        self.assertEqual(spec["parameters"]["min_replicates"], 2)
        self.assertIn("USER_SETTINGS_FILE", docs["config/rnaseq_pipeline_config.sh"])
        self.assertIn("pipelines/rnaseq/config/pipeline_config.sh", docs["config/rnaseq_pipeline_config.sh"])
        self.assertNotIn("/config/user_settings.sh", docs["run.config"])
        self.assertEqual(submission.submission_from_plan(generated["plan"])["config"], "/home/researcher/projects/analysis-01/run.config")

    def test_chipseq_metadata_and_db_spec_preserve_controls(self):
        _, docs = self.documents("chipseq")
        self.assertIn("control_id\tis_control\torganism\tgenome_id", docs["config/chipseq_metadata.tsv"].splitlines()[0])
        self.assertIn("input_1", docs["config/chipseq_metadata.tsv"])
        spec = json.loads(docs["specifications/differential_binding.json"])
        self.assertEqual(spec["provider"], "deseq2")
        self.assertEqual(spec["design"]["covariates"], ["batch"])
        self.assertIn("export ALIGNER=bowtie2", docs["config/chipseq_user_settings.sh"])
        self.assertIn("export MACS_GENOME_SIZE=2913022398", docs["config/chipseq_user_settings.sh"])
        self.assertIn("chipseq_consensus_method = 'replicate_support'", docs["run.config"])

    def test_all_generates_both_assays_and_repository_policy_templates(self):
        _, docs = self.documents("all")
        self.assertIn("config/rnaseq_metadata.tsv", docs)
        self.assertIn("config/chipseq_metadata.tsv", docs)
        self.assertEqual(docs["policies/harmonization_policy.json"], (ROOT / "assets/integration/harmonization_policy.v1.json").read_text(encoding="utf-8"))
        self.assertIn("integrative_harmonization_policy", docs["run.config"])

    def test_integrative_uses_manifests_without_requesting_upstream_samples(self):
        plan = base_plan("integrative")
        plan["organism"] = {"name":"", "reference_id":"", "genome_fasta":"", "transcriptome_fasta":"", "annotation":"", "blacklist":""}
        generated = submission.generate_documents(plan)
        docs = {item["relative_path"]:item["content"] for item in generated["documents"]}
        self.assertIn("rna_manifest = '/scratch/rna/rnaseq_run_manifest.json'", docs["run.config"])
        self.assertEqual(generated["plan"]["samples"], {"rnaseq":[], "chipseq":[]})

    def test_integrative_can_select_existing_policy_files(self):
        plan = base_plan("integrative")
        plan["organism"] = {"name":"", "reference_id":"", "genome_fasta":"", "transcriptome_fasta":"", "annotation":"", "blacklist":""}
        names = ("harmonization", "interpretation", "mark_roles", "prioritization_context", "functional_annotation")
        plan["integration"].update(policy_mode="custom", policy_paths={name:f"/home/researcher/policies/{name}" for name in names})
        generated = submission.generate_documents(plan)
        config = next(item["content"] for item in generated["documents"] if item["relative_path"] == "run.config")
        self.assertIn("integrative_harmonization_policy = '/home/researcher/policies/harmonization'", config)
        self.assertIn("/home/researcher/policies/functional_annotation", submission.input_paths(generated["plan"]))

    def test_malicious_paths_cells_and_repository_are_rejected(self):
        cases = []
        plan = base_plan(); plan["storage"]["output"] = "/scratch/../escape"; cases.append(plan)
        plan = base_plan(); plan["rnaseq_samples"][0]["sample_id"] = "sample\tbad"; cases.append(plan)
        plan = base_plan(); plan["clone"] = {"mode":"new", "path":"/home/new", "repository":"https://evil.invalid/repo", "ref":"main"}; cases.append(plan)
        for plan in cases:
            with self.subTest(plan=plan), self.assertRaises(submission.PlanError): submission.generate_documents(plan)

    def test_ip_control_batch_and_replicate_validation(self):
        plan = base_plan("chipseq"); plan["chipseq_samples"][1]["control_id"] = "missing"
        with self.assertRaisesRegex(submission.PlanError, "controle existente"): submission.validate_plan(plan)
        plan = base_plan("rnaseq"); plan["statistics"]["formula"] = "~ condition"
        with self.assertRaisesRegex(submission.PlanError, "covariáveis"): submission.validate_plan(plan)
        plan = base_plan("rnaseq"); plan["rnaseq_samples"] = plan["rnaseq_samples"][:2]
        with self.assertRaisesRegex(submission.PlanError, "replicatas"): submission.validate_plan(plan)

    def test_star_is_explicit_and_idr_requires_narrow_peaks(self):
        plan = base_plan("rnaseq"); plan["science"]["quantification"] = "star"; plan["organism"]["genome_fasta"] = ""
        with self.assertRaisesRegex(submission.PlanError, "Campo obrigatório"): submission.validate_plan(plan)
        plan = base_plan("chipseq"); plan["science"].update(idr=True, peak_type="broad")
        with self.assertRaisesRegex(submission.PlanError, "IDR requer picos narrow"): submission.validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
