import json
import os

UPDATE_MAP = {
    "vs-1072": {"keywords": ["vendor services", "what is", "overview", "epic program"], "synonyms": ["support program", "developer integration", "epic membership"]},
    "vs-1073": {"keywords": ["users", "developers", "customers", "who uses"], "synonyms": ["website users", "target audience"]},
    "vs-1075": {"keywords": ["enroll", "register", "sign up", "join", "get started"], "synonyms": ["enrollment", "registration", "application", "onboarding"]},
    "vs-1278": {"keywords": ["account setup", "how long", "timeline", "48 hours", "interested form"], "synonyms": ["account creation time", "registration duration"]},
    "vs-1076": {"keywords": ["cost", "pricing", "price", "fees", "annual fee", "1900", "$1900", "how much"], "synonyms": ["subscription cost", "membership price", "billing"]},
    "vs-1078": {"keywords": ["trial", "trial period", "cancel", "refund", "three months"], "synonyms": ["free trial", "money back", "cancellation policy"]},
    "vs-1100": {"keywords": ["learning", "training", "tutorials", "forum", "sherlock", "networking", "webinar", "education"], "synonyms": ["resources", "developer forum", "peer learning"]},
    "vs-1088": {"keywords": ["data exchange", "interoperability", "interface", "API", "third party", "integration"], "synonyms": ["data sharing", "system integration", "interop"]},
    "vs-1098": {"keywords": ["standards", "HL7", "FHIR", "X12", "CDA", "DICOM", "NCPDP", "industry standards"], "synonyms": ["healthcare standards", "interoperability standards"]},
    "vs-1089": {"keywords": ["API", "APIs", "endpoints", "FHIR", "SMART", "CDS Hooks", "web services"], "synonyms": ["application programming interface", "API catalog", "specifications"]},
    "vs-1090": {"keywords": ["FHIR", "HL7 FHIR", "resources", "read write", "fhir support"], "synonyms": ["fast healthcare interoperability resources", "FHIR API"]},
    "vs-1092": {"keywords": ["SMART on FHIR", "OAuth 2.0", "OAuth", "single sign on", "SSO", "launch", "EHR launch"], "synonyms": ["OAuth authentication", "app authorization", "SMART launch"]},
    "vs-1094": {"keywords": ["CDS Hooks", "clinical decision support", "order sign", "patient view", "workflow"], "synonyms": ["decision support hooks", "CDS"]},
    "vs-1096": {"keywords": ["clinical content", "knowledge vendors", "decision support", "nursing", "patient instructions"], "synonyms": ["clinical knowledge", "content vendors"]},
    "vs-1097": {"keywords": ["analytics", "machine learning", "ML", "predictive", "Caboodle", "Kit", "data warehouse"], "synonyms": ["AI vendors", "data analytics", "ML integration"]},
    "vs-1112": {"keywords": ["buy", "purchase", "sell", "sales", "pricing", "invoice", "customers"], "synonyms": ["customer purchase", "sales process"]},
    "vs-1115": {"keywords": ["trademark", "logo", "brand", "guidelines", "usage", "Epic trademark"], "synonyms": ["brand guidelines", "logo usage"]},
    "vs-3516": {"keywords": ["Connection Hub", "listing", "app listing", "Showroom", "live connection", "request listing"], "synonyms": ["marketplace listing", "app marketplace"]},
    "vs-1119": {"keywords": ["user account", "account", "UserWeb", "admin", "provision", "get access", "staff account"], "synonyms": ["create account", "new user", "account provisioning"]},
    "vs-1120": {"keywords": ["log in", "login", "sign in", "credentials", "UserWeb", "SSO", "Windows password"], "synonyms": ["authenticate", "access site", "login steps"]},
    "vs-1121": {"keywords": ["trouble", "can't login", "forgot password", "forgot username", "reset password", "locked out", "access issue"], "synonyms": ["password reset", "login help", "account recovery", "access denied"]},
    "vs-9797": {"keywords": ["implementation", "implement", "go live", "deployment", "IT", "operations", "stakeholders"], "synonyms": ["app deployment", "integration rollout"]},
    "vs-1240": {"keywords": ["testing", "sandbox", "test harness", "Hyperspace", "Hyperdrive", "try-it", "MyChart", "tools"], "synonyms": ["QA tools", "test environment", "developer sandbox"]},
    "vs-1265": {"keywords": ["design", "assistance", "support", "TS", "technical specialist", "workflow design"], "synonyms": ["design help", "integration design", "technical support"]},
    "vs-5797": {"keywords": ["Showroom", "marketplace", "discover", "products", "listing"], "synonyms": ["Epic marketplace", "app store", "product catalog"]},
    "vs-5798": {"keywords": ["Showroom", "tiers", "Cornerstone", "Toolbox", "Workshop", "Connection Hub", "tier differences"], "synonyms": ["product tiers", "listing levels", "Showroom categories"]},
    "vs-5815": {"keywords": ["Showroom", "designation", "change", "evaluate", "Toolbox", "Workshop"], "synonyms": ["tier upgrade", "category change"]},
    "vs-5800": {"keywords": ["open.epic", "Epic on FHIR", "Vendor Services", "Showroom", "differences", "compare", "which one"], "synonyms": ["platform comparison", "resource comparison"]},
    "vs-1125": {"keywords": ["contact", "reach", "support", "email", "Sherlock", "phone", "how to contact"], "synonyms": ["get in touch", "customer support", "technical support contact"]},
    "vs-1126": {"keywords": ["contact", "address", "phone number", "email", "Verona", "Wisconsin"], "synonyms": ["Epic address", "phone", "mailing address"]},
}

file_path = r"c:\Users\navne\FAQ_Project\epic-vendor-copilot\SEED_DATA\epic_vendor_faq.json"

with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

for section in data.get("sections", []):
    for entry in section.get("entries", []):
        eid = entry.get("id")
        
        # Make sure keywords and synonyms exist, guard against None
        entry["keywords"] = entry.get("keywords") or []
        entry["synonyms"] = entry.get("synonyms") or []
        
        if eid in UPDATE_MAP:
            updates = UPDATE_MAP[eid]
            for kw in updates["keywords"]:
                if kw not in entry["keywords"]:
                    entry["keywords"].append(kw)
            for syn in updates["synonyms"]:
                if syn not in entry["synonyms"]:
                    entry["synonyms"].append(syn)

with open(file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Updates applied.")
