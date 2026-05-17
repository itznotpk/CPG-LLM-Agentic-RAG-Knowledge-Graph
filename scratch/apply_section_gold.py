"""
Replace `relevant_chunk_ids` in eval/gold_sets/retrieval_gold.jsonl for the
22 resolved questions with chunk IDs picked BY HAND from the source markdown
sections (not by running the retriever). See scratch/chunk_dump.txt for the
candidate set used during labelling.
"""
import json, os

GOLD = "eval/gold_sets/retrieval_gold.jsonl"

# Manually labelled gold: question id -> list of chunk UUIDs (top-3 sections
# from the source markdown that genuinely answer the question).
GOLD_MAP = {
    "ret_030": [
        "4a357abd-f6a2-4fb3-b6c5-9446563d340d",  # 6.1 Risk Stratification (CHA2DS2-VASc/CHADS2)
        "c28f691c-b9f5-4a94-95d1-6314d736ffc1",  # 6.2 Strategies for Thromboembolic Prophylaxis
        "a2fb566d-409e-4b9f-8bc4-20d18d70e18d",  # 4.2 Thromboembolic Prophylaxis
    ],
    "ret_031": [
        "b57540a7-b817-4c1b-af33-230b71bfc89d",  # 6.3.3 Direct Thrombin Inhibitors (dabigatran)
        "29da79c0-d122-4dbd-8358-49833abb778c",  # 6.3.4 Investigational Agents (Xa inhibitors)
        "c28f691c-b9f5-4a94-95d1-6314d736ffc1",  # 6.2 Strategies (NOAC vs VKA choice)
    ],
    "ret_032": [
        "c002a270-4e8f-4ec0-9c51-27efdd840d0f",  # 9.10 Valvular Heart Disease
        "459eb0c5-c815-41c2-b202-c066f6591b49",  # 6.3.1 VKA — when warfarin is required
        "b57540a7-b817-4c1b-af33-230b71bfc89d",  # 6.3.3 Direct Thrombin Inhibitors (NOAC contraindications)
    ],
    "ret_033": [
        "4350ba43-ac39-43b4-895b-c562c1ee986d",  # 7.1.1 Rate Control Targets and Strategy
        "d3f61a5f-1e14-4cec-b144-9b75cbdadef7",  # 7.1.2 Choice of Rate-Control Agent
        "0604b79d-cbb1-4045-9852-f5fb4f0a61c6",  # 7.1.3 Recommendations
    ],
    "ret_034": [
        "d9a14188-1c01-41c7-8344-39b4c1382139",  # 6.4.5 Cardioversion (anticoagulation around cardioversion)
        "02bc64bf-023c-405b-b3f6-e714a2d5f5dc",  # 5.1.3 DCCV
        "068c280a-774f-4724-b8a6-503f7348baf2",  # 5.1.2 Pharmacological Cardioversion
    ],
    "ret_064": [
        "45bf206f-f4e6-49f0-9372-51b5e25337fe",  # 4.2 WHO Analgesic Ladder
        "58dc7be3-f924-4a9e-9a1d-102fc770811c",  # Algorithm 1: Mgmt of Cancer Pain in Adults (3-step)
        "45174b74-4871-43f9-b8d1-09bbcaca4f4e",  # 4.3 Non-Opioids (Step 1)
    ],
    "ret_065": [
        "3dab2948-44a8-41fd-b688-b44fe9fb0359",  # 4.4.4 Breakthrough Pain Management
        "152dfa30-358e-45a2-b5c5-4d30867f0c8b",  # 4.4.3 Opioid Initiation, Titration, Maintenance
        "e48a1e6a-d61e-4d3c-898b-3229159cd049",  # Algorithm 2: Titration of Morphine
    ],
    "ret_066": [
        "8e6b5dfc-2f8b-4679-93e9-fa37578ba169",  # 4.5 Anticonvulsants (gabapentin/pregabalin)
        "5545104c-31da-4fd5-b56e-d73194954c37",  # 4.5 Antidepressants (amitriptyline/duloxetine)
        "7aabd626-4dc3-47d5-913e-ce0c92588211",  # 4.5 Corticosteroids
    ],
    "ret_067": [
        "b5a6f792-61af-44db-8956-fb646781203d",  # 4.4.8 Opioid Side Effects (constipation prophylaxis)
        "6af3d586-2280-4184-9f63-ba7346d69507",  # Appendix 5A Medication Dosages (laxatives)
        "58dc7be3-f924-4a9e-9a1d-102fc770811c",  # Algorithm 1 (prophylactic laxative step)
    ],
    "ret_072": [
        "eb606127-4d11-42d1-a64e-6df77e520844",  # 3.1 General Monitoring Principles
        "fb0bceca-58e2-4daa-9d4a-3a343b81ac62",  # 3.2 Oxygenation (SpO2)
        "75376fad-db80-4add-8548-48ffbe6b1a5f",  # 3.3 Circulation (BP, HR, ECG)
    ],
    "ret_073": [
        "5faa2c3d-bfcc-4a82-91a2-be319e174b5b",  # 3.5 Temperature
        "eb606127-4d11-42d1-a64e-6df77e520844",  # 3.1 General Monitoring Principles
        "717ad6db-5c59-46c5-8b0a-db883d0d7206",  # 5.2 Standards of Care And Monitoring (equivalent care)
    ],
    "ret_074": [
        "8abf42d7-852e-4012-bd1b-00d1ddc452f5",  # 4.3 Monitoring in Recovery
        "90adec0f-abce-4ac6-9b21-acf7f64dd220",  # 4.2 Minimum Facilities for Recovery Area
        "fe7f208d-e209-4228-9d13-8ac9397c0798",  # 4.4 Handover and Discharge (Aldrete)
    ],
    "ret_075": [
        "7634c215-9aa1-46d6-9770-a874e3242e4d",  # Section 4 Risk Assessment, Stratification (ASA)
        "d95ac0af-3a23-42a2-8f8f-beda7186a549",  # 3.2 Physical Examination
        "959c2791-2988-42df-a3cb-b7d59066c797",  # Appendix: Pre-Anaesthetic Investigations
    ],
    "ret_076": [
        "b5808984-102b-4f6d-bc5e-3c4a4d87e2ec",  # 8.3 Pre-Operative Fasting (paediatric, but covers windows)
        "8b52edab-ee0a-40da-aa1e-bb33e11d3a3d",  # Section 7 Documentation (incl. preop fasting)
        "5b52e8a2-5c1a-4668-be12-f2f53a2941ba",  # 3.4 Others (selective preparation)
    ],
    "ret_077": [
        "7634c215-9aa1-46d6-9770-a874e3242e4d",  # Section 4 Risk Assessment, Stratification (RCRI, ASA)
        "959c2791-2988-42df-a3cb-b7d59066c797",  # Appendix: Pre-Anaesthetic Investigations
        "d95ac0af-3a23-42a2-8f8f-beda7186a549",  # 3.2 Physical Examination
    ],
    "ret_078": [
        "96bb3ca9-83c5-453d-983e-86b8eae9300e",  # Section 6 Pre-Operative Medication
        "e3d94e8a-f13a-49d7-85ca-dbe1bd90babb",  # 8.4 Premedication (paediatric premed)
        "b5808984-102b-4f6d-bc5e-3c4a4d87e2ec",  # 8.3 Pre-Operative Fasting (related)
    ],
    "ret_079": [
        "c992f582-2a25-4f87-963e-8ba98c2c5a25",  # 2.10 Admin of Highly Concentrated Drugs/Electrolytes/Insulin
        "8909e0b9-b45e-49a8-a73d-a3650c48e689",  # 2.6 Anaesthesia Medication Storage (locked dangerous drugs)
        "ad251779-91ed-4cf1-920a-18e6f9809657",  # 1.1 Background (high-alert principles)
    ],
    "ret_080": [
        "37df16cc-9b39-49e6-a748-925862e1bc92",  # 3.1.5 Use of NMBA (neuromuscular monitoring)
        "834cede3-9454-415b-a7cc-325a0d4a4ef0",  # 4.4 Extreme Body Weight (NMBA dosing in obese)
        "b29dc24f-e713-4615-ba3b-60e995f27f32",  # 3.1.1 Inhalational/General Anaesthesia handling
    ],
    "ret_081": [
        "195b0526-7e58-4840-9b2b-d663a0877f80",  # 2.8 Medication Labelling (syringe labelling per national std)
        "12b5bfcf-928c-4ab8-b160-7bf7c1970c6b",  # 2.7 Medication Preparation and Verification
        "95c35397-81c1-4417-859e-680a1d2dc89a",  # 2.11 IV Medication Delivery (label placement)
    ],
    "ret_082": [
        "cea71eb0-d197-480f-86b6-9e6f59b9e5e6",  # 5.1.1 Perioperative Hypersensitivity Introduction
        "174c2427-684f-477b-8868-8c5036af03aa",  # 5.1.2 Management of POA reactions
        "5f8a77a3-14c8-4552-855d-4116ebf93eaa",  # 5.1.5 Managing suspected reaction cases
    ],
    "ret_104": [
        "14523e40-56f5-48e7-998f-025f2518b62f",  # 4.4.5 Opioid Rotation
        "152dfa30-358e-45a2-b5c5-4d30867f0c8b",  # 4.4.3 Opioid Initiation/Titration/Maintenance
        "b5a6f792-61af-44db-8956-fb646781203d",  # 4.4.8 Opioid Side Effects (drives rotation decisions)
    ],
    "ret_113": [
        "74f4a084-7315-41ce-af3d-51ec9be7baeb",  # 6.4.1 Perioperative Anticoagulation
        "e8d5508f-765b-45ef-ab08-cf8221c94b7c",  # Appendix C.12 Interruption of Warfarin for Surgery
        "48eda19f-52b2-4ad0-95a6-34917587f8d6",  # Appendix C.11 Managing Elevated INRs/Bleeding
    ],
}


def main():
    with open(GOLD, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    updated = 0
    for r in rows:
        if r["id"] in GOLD_MAP:
            r["relevant_chunk_ids"] = GOLD_MAP[r["id"]]
            r["label_provenance"] = "hand-mapped from markdown sections (scratch/apply_section_gold.py)"
            updated += 1

    with open(GOLD, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Updated {updated} / {len(GOLD_MAP)} expected. Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
