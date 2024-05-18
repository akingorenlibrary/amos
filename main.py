import os
from collections import Counter
kelime_sayaci = Counter()

dosya_dizini = 'C:/Users/betlb/source/repos/amos/makaleonerisistemi/Inspec/keys'  # Değiştirin

for dosya_adi in os.listdir(dosya_dizini):
    dosya_yolu = os.path.join(dosya_dizini, dosya_adi)
    if os.path.isfile(dosya_yolu) and dosya_adi.endswith('.key'):
        with open(dosya_yolu, 'r', encoding='utf-8') as file:
            kelimeler = file.read().splitlines()
            kelime_sayaci.update(kelimeler)

en_sik_kelimeler = kelime_sayaci.most_common(50)

# Sonuçları yazdırma
for kelime, sayi in en_sik_kelimeler:
    print(f'{kelime}: {sayi}')
