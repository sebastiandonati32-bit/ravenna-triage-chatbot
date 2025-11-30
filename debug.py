import os

# Trova la cartella corrente
base_dir = os.path.dirname(os.path.abspath(__file__))
kb_dir = os.path.join(base_dir, "knowledge_base")

print(f"📂 SONO DENTRO: {base_dir}")
print("-" * 30)

# Controlla Fase 1
p1 = os.path.join(kb_dir, "phase_1_safety")
if os.path.exists(p1):
    print(f"✅ Cartella phase_1 trovata. Contiene: {os.listdir(p1)}")
else:
    print(f"❌ Cartella phase_1 NON trovata. Cerco qui: {p1}")

# Controlla Fase 3
p3 = os.path.join(kb_dir, "phase_3_logistics")
if os.path.exists(p3):
    print(f"✅ Cartella phase_3 trovata. Contiene: {os.listdir(p3)}")
else:
    print(f"❌ Cartella phase_3 NON trovata. Cerco qui: {p3}")