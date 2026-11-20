"""build_knowledge.py - creates data/knowledge.json (precautions + diet for every disease)
Format of each line:  Disease | urgency | precautions separated by ; | diet advice
urgency: emergency = go to hospital now, soon = see a doctor within 1-2 days, routine = see a doctor when possible"""
import json
RAW = """
Vertigo (Positional)|routine|Sit or lie down when dizzy; Avoid sudden head movements; Do not drive during an episode; Ask a doctor about head-position exercises|Drink enough water; Cut down salt, caffeine and alcohol; Eat regular small meals
AIDS|soon|Get tested and start treatment under a doctor; Never share needles or razors; Use protection; Take medicines exactly on time|High-protein balanced meals; Fresh fruit and vegetables; Safe, well-cooked food and clean water
Acne|routine|Wash face twice a day with a mild cleanser; Do not squeeze pimples; Keep hair and phone clean; See a skin doctor if it is severe|Fewer sugary and fried foods; More vegetables, fruit and water; Limit dairy if it worsens acne
Alcoholic hepatitis|soon|Stop alcohol completely; See a doctor for liver tests; Avoid unprescribed painkillers; Get vaccinated for hepatitis A and B|Small high-protein meals; Fruit and vegetables; No alcohol and little salt
Allergy|routine|Find and avoid the trigger; Keep rooms dust-free; Carry the antihistamine your doctor advised; Seek help at once for swelling or breathing trouble|Note foods that trigger symptoms; Fresh home-cooked meals; Foods rich in vitamin C
Arthritis|routine|Gentle daily exercise and stretching; Use warm packs on stiff joints; Protect joints from strain; Follow your doctor's treatment plan|Fish, nuts, olive oil; Colourful fruit and vegetables; Fewer sugary and processed foods
Bronchial Asthma|soon|Avoid dust, smoke and cold air; Keep your inhaler with you; Know your triggers; Go to hospital if breathing becomes very hard|Warm fluids; Fruit and vegetables rich in vitamins C and E; Avoid foods that trigger you
Cervical spondylosis|routine|Fix your sitting and screen posture; Do neck stretches advised by a physiotherapist; Use a firm, low pillow; Avoid long periods looking down|Calcium rich foods like milk and ragi; Vitamin D from sunlight and eggs; Plenty of water
Chicken pox|soon|Stay at home and away from others; Do not scratch the blisters; Keep nails short; Ask a doctor about fever medicine|Soft, cool foods; Lots of fluids; Fruit rich in vitamin C
Chronic cholestasis|soon|See a liver specialist; Avoid alcohol; Avoid medicines that harm the liver; Report dark urine or pale stools|Low-fat meals; Fruit and vegetables; Ask a doctor about vitamin supplements
Common Cold|routine|Rest and keep warm; Wash hands often; Cover your cough; See a doctor if fever lasts more than 3 days|Warm soup and fluids; Ginger, honey and lemon tea; Foods rich in vitamin C
Dengue|emergency|See a doctor and get a blood test; Rest completely; Use mosquito nets and repellent; Go to hospital for bleeding, vomiting or severe stomach pain; Do not take aspirin or ibuprofen|Lots of fluids and ORS; Coconut water; Light easily digested food
Piles (Hemorrhoids)|routine|Do not strain on the toilet; Do not sit for a long time; Warm sitz bath; See a doctor if there is bleeding|High-fibre food like oats, fruit and vegetables; 8 to 10 glasses of water; Cut down spicy food
Drug Reaction|emergency|Stop the suspected medicine and call a doctor; Go to hospital for swelling or breathing trouble; Tell every doctor about this reaction; Do not restart the medicine|Plain light meals; Plenty of water; Avoid alcohol
Fungal infection|routine|Keep the skin clean and dry; Wear loose cotton clothes; Do not share towels; Use the antifungal a doctor advises|Fewer sugary foods; Curd and probiotic food; Plenty of vegetables
GERD|routine|Eat small meals; Do not lie down for 2 hours after eating; Raise the head of your bed; Avoid smoking and tight clothes|Avoid spicy, oily and fried food; Cut down tea, coffee and fizzy drinks; Oats, bananas and non-citrus fruit
Gastroenteritis|soon|Drink ORS often; Wash hands and use clean water; Rest; See a doctor if there is blood, high fever or no urine|ORS and clear fluids; Banana, rice, toast, curd; Avoid dairy, spicy and oily food for a few days
Heart attack|emergency|Call an emergency number immediately; Sit down and stay calm; Do not walk or drive yourself; Take aspirin only if a doctor has told you to|After recovery: low salt and low oil; Fruit, vegetables, whole grains and fish; No smoking
Hepatitis B|soon|See a doctor for blood tests; Do not share needles or razors; Use protection; Get family members vaccinated|Balanced meals with enough protein; Fruit and vegetables; No alcohol
Hepatitis C|soon|See a doctor for blood tests and treatment; Do not share needles or razors; Avoid alcohol; Cover cuts and wounds|Balanced meals; Low salt; No alcohol
Hepatitis D|soon|See a doctor urgently for tests; Get vaccinated for hepatitis B; Do not share needles or razors; Avoid alcohol|Balanced low-fat meals; Fruit and vegetables; No alcohol
Hepatitis E|soon|Drink only boiled or safe water; Wash hands before eating; Rest well; See a doctor, especially if pregnant|Light low-fat meals; Plenty of fluids; Fresh, well-cooked food
Hypertension|soon|Check blood pressure regularly; Take medicines as prescribed; Walk 30 minutes most days; Stop smoking and reduce stress|Cut salt strictly; More fruit, vegetables and whole grains; Fewer pickles, chips and processed food
Hyperthyroidism|soon|See a doctor for thyroid tests; Avoid caffeine and smoking; Manage stress; Report a fast heartbeat or chest pain|Enough calories and calcium; Avoid too much iodine-rich food; Limit tea and coffee
Hypoglycemia|emergency|Take quick sugar such as juice or glucose if you are conscious; Eat regular meals; Check blood sugar; Get urgent help if you faint or cannot swallow|Regular small meals; Whole grains with protein; Keep a sweet snack with you
Hypothyroidism|routine|Take thyroid medicine daily on an empty stomach; Get regular thyroid tests; Exercise regularly; Do not stop medicine without advice|Foods with iodine and selenium; High-fibre meals; Avoid large amounts of raw cabbage and soy
Impetigo|soon|Keep sores clean and covered; Do not scratch; Do not share towels; See a doctor for antibiotic cream|Balanced meals; Vitamin C foods; Plenty of water
Jaundice|soon|See a doctor for liver tests; Rest; Drink only safe water; Avoid alcohol and unprescribed medicines|Light low-fat meals; Sugarcane juice and fresh fruit; Avoid oily and spicy food
Malaria|emergency|Get a blood test and treatment immediately; Take the full medicine course; Use mosquito nets and repellent; Drain standing water around the house|Plenty of fluids and ORS; Light, easily digested food; Fruit and glucose drinks
Migraine|routine|Rest in a dark, quiet room; Keep a regular sleep time; Note your triggers; See a doctor if headaches are frequent or sudden and severe|Do not skip meals; Drink plenty of water; Cut down caffeine, cheese and chocolate if they trigger you
Osteoarthritis|routine|Keep the weight healthy; Gentle exercise such as walking or swimming; Use warm packs; Wear supportive footwear|Calcium and vitamin D; Fish, nuts and olive oil; Fruit and vegetables
Paralysis (Brain hemorrhage)|emergency|Call an emergency number immediately; Do not give food or water; Note the time symptoms began; Keep the person lying down and calm|After recovery: low salt and low fat; Fruit, vegetables and whole grains; Doctor-guided diet
Peptic ulcer disease|soon|Avoid painkillers like ibuprofen unless advised; Stop smoking and alcohol; Eat on time; See a doctor to test for H. pylori|Small frequent meals; Avoid spicy food, tea and coffee; Banana, oats, curd
Pneumonia|soon|See a doctor today; Take antibiotics as prescribed; Rest and drink fluids; Go to hospital for fast breathing or blue lips|Warm fluids and soups; Protein-rich food; Fruit rich in vitamin C
Psoriasis|routine|Moisturise skin daily; Avoid scratching and harsh soaps; Manage stress; See a skin doctor for treatment|Fish, fruit and vegetables; Fewer red meat and sugary foods; No alcohol
Tuberculosis|soon|See a doctor and complete the full medicine course; Cover your mouth when you cough; Keep rooms ventilated; Test close family members|High-protein meals such as dal, eggs, milk; Fruit and vegetables; Plenty of fluids
Typhoid|soon|See a doctor for a blood test and antibiotics; Drink boiled or safe water; Wash hands; Rest fully|Soft, easily digested food; Boiled water and ORS; Avoid raw and street food
Urinary tract infection|soon|Drink plenty of water; Do not hold urine; See a doctor for antibiotics; Keep the genital area clean|Water, 2 to 3 litres a day; Fruit rich in vitamin C; Cut down caffeine and spicy food
Varicose veins|routine|Walk daily; Raise your legs when resting; Avoid standing or sitting for long; Ask about compression stockings|Fibre-rich food; Less salt; Keep the weight healthy
Diabetes|soon|See a doctor for fasting sugar and HbA1c tests; Check blood sugar regularly; Walk 30 minutes daily; Look after your feet and eyes|No sugar or sweet drinks; Oats, millets, dal and vegetables; Regular small meals
Hepatitis A|soon|Rest and drink safe water; Wash hands before eating; See a doctor for liver tests; Avoid alcohol|Light low-fat meals; Plenty of fluids; Fresh, well-cooked food
"""
disease = {}
for line in RAW.strip().splitlines():
    name, urgency, prec, diet = [x.strip() for x in line.split("|")]
    disease[name] = {"urgency": urgency,
                     "precautions": [p.strip() for p in prec.split(";")],
                     "diet": [d.strip() for d in diet.split(";")]}

risk_advice = {
    "heart": {
        "Low": {"precautions": ["Keep a regular check-up every year", "Stay active 30 minutes a day", "Do not smoke"],
                "diet": ["Fruit, vegetables and whole grains", "Limit fried and processed food", "Keep salt low"]},
        "Intermediate": {"precautions": ["Check blood pressure and cholesterol every 3 months", "Walk or exercise 30 to 45 minutes most days", "Stop smoking and reduce stress", "See a doctor for a heart check-up"],
                         "diet": ["Cut salt and oily food", "Oats, fish, nuts and olive oil", "More fruit and vegetables"]},
        "High": {"precautions": ["See a doctor or cardiologist soon for an ECG and tests", "Go to hospital at once for chest pain, sweating or breathlessness", "Stop smoking and alcohol", "Take prescribed medicines on time"],
                 "diet": ["Very low salt and low oil", "Whole grains, fish, fruit and vegetables", "Avoid red meat, sweets and fast food"]}},
    "diabetes": {
        "Low": {"precautions": ["Test blood sugar once a year", "Stay active and keep a healthy weight", "Sleep 7 to 8 hours"],
                "diet": ["Whole grains instead of white rice and bread", "Fewer sweet drinks", "More vegetables and protein"]},
        "Intermediate": {"precautions": ["Get a fasting sugar and HbA1c test", "Lose 5 to 7 percent of body weight if overweight", "Walk 30 minutes daily", "Recheck sugar every 3 to 6 months"],
                         "diet": ["Cut sugar, sweets and sweet drinks", "Whole grains, dal, vegetables", "Smaller portions of rice and roti"]},
        "High": {"precautions": ["See a doctor soon for sugar tests and treatment", "Check blood sugar regularly", "Look after your feet and eyes", "Seek help at once for extreme thirst, vomiting or confusion"],
                 "diet": ["No sugar or sweet drinks", "Low-GI food: oats, millets, dal, vegetables", "Regular small meals, do not skip meals"]}},
}
SPECIALIST = {"Vertigo (Positional)":"ENT specialist","AIDS":"infectious disease specialist","Acne":"dermatologist","Alcoholic hepatitis":"gastroenterologist","Allergy":"allergy specialist","Arthritis":"rheumatologist","Bronchial Asthma":"pulmonologist","Cervical spondylosis":"orthopedic doctor","Chronic cholestasis":"gastroenterologist","GERD":"gastroenterologist","Gastroenteritis":"gastroenterologist","Heart attack":"cardiologist","Hepatitis A":"gastroenterologist","Hepatitis B":"gastroenterologist","Hepatitis C":"gastroenterologist","Hepatitis D":"gastroenterologist","Hepatitis E":"gastroenterologist","Hypertension":"cardiologist","Hyperthyroidism":"endocrinologist","Hypothyroidism":"endocrinologist","Hypoglycemia":"endocrinologist","Impetigo":"dermatologist","Fungal infection":"dermatologist","Psoriasis":"dermatologist","Jaundice":"gastroenterologist","Migraine":"neurologist","Osteoarthritis":"orthopedic doctor","Paralysis (Brain hemorrhage)":"neurologist","Peptic ulcer disease":"gastroenterologist","Piles (Hemorrhoids)":"proctologist","Pneumonia":"pulmonologist","Tuberculosis":"pulmonologist","Urinary tract infection":"urologist","Varicose veins":"vascular surgeon","Diabetes":"diabetologist"}
for _n, _v in disease.items():
    _v["specialist"] = SPECIALIST.get(_n, "general physician")   # Chicken pox, Cold, Dengue, Malaria, Typhoid, Drug reaction
risk_advice["heart"]["specialist"] = "cardiologist"
risk_advice["diabetes"]["specialist"] = "diabetologist"
json.dump({"diseases": disease, "risk_advice": risk_advice}, open("data/knowledge.json", "w"), indent=1, ensure_ascii=False)
prof = json.load(open("models/symptom_profiles.json"))["profiles"]
missing = [d for d in prof if d not in disease]
print(len(disease), "diseases written; missing:", missing)
