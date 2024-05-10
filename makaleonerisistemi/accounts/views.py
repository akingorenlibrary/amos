from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import UserCreationForm
import logging
from django.contrib import messages
from pymongo import MongoClient
from django.contrib.auth import authenticate, login, get_user_model, logout
from django.contrib.auth.hashers import check_password
import nltk
import tokenizer as tokenizer
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import SnowballStemmer
import string
from transformers import AutoTokenizer, AutoModel
import numpy as np
import fasttext
import fasttext.util
import os
import torch
from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

# MongoDB'ye baglan
client = MongoClient('localhost', 27017)
db = client['amosdb']  # MongoDB veritabani adi
users_collection = db['users']  # Kullanici koleksiyonu
makale_collection = db['articles']  # Makale koleksiyonu


#nltk.download('punkt')# bunu bir kere indirmeliyiz
#nltk.download('stopwords')# bunu bir kere indirmeliyiz

fasttext.util.download_model("en", if_exists="ignore")# bu model i�in bir kere indirdikten sonra kapatilacak
fasttext_model = fasttext.load_model('cc.en.300.bin')
fasttext_tokenizer = fasttext.tokenize('cc.en.300.bin')

print("a46")
scibert_tokenizer = AutoTokenizer.from_pretrained("allenai/scibert_scivocab_uncased")
scibert_model = AutoModel.from_pretrained("allenai/scibert_scivocab_uncased")
print("a45")


def userRegister(request):#EKLEME: buraya kullanici ilgi alanlariyla birlikte fasttext ve scibert vektorleri eklenmeli. guncelleme islemindede duzenleme yapilmali
    ##!!! her vektor icin 300 ve 700 vektor var bunu arastir
    if request.method == 'POST':
        # Formdan gelen verileri al
        fullname = request.POST.get('fullname')
        email = request.POST.get('email')
        password = request.POST.get('password')
        ilgi_alanlari = request.POST.getlist('ilgi_alanlari')  # Coklu secimleri al
        ft_kullanici_vektor=kullaniciVektorF(ilgi_alanlari).tolist()
        sb_kullanici_vektor=kullaniciVektorS(ilgi_alanlari).tolist()
        # Veri kontrolu yap
        if fullname and email and password and ilgi_alanlari:
            # MongoDB'ye kaydet
            users_collection = db['users']  # Koleksiyon adi
            user_data = {
                'fullname': fullname,
                'email': email,
                'password': password,
                'ilgi_alanlari': ilgi_alanlari,
                'fasttext':ft_kullanici_vektor,
                'scibert':sb_kullanici_vektor
            }
            users_collection.insert_one(user_data)
            
            # Basarili kayit olduktan sonra baska bir sayfaya yonlendir
            return redirect('login')  # 'home' isimli URL'ye yonlendir
        else:
            # Hata mesaji goster
            messages.error(request, 'Lütfen tüm alanları doldurun.')
    
    return render(request, 'register.html')  # GET request oldugunda register.html sayfasini goster

def home(request):
    return render(request, "index.html")


def dashboard(request):
    if 'user_email' in request.session:
        
        # Kullanici oturumu acik ise dashboard sayfasini goster
        user_data = users_collection.find_one({'email': request.session['user_email']})
        if user_data:
            ialanlari=str(user_data.get('ilgi_alanlari'))
            #processed_textF = kullaniciVektorF(ialanlari)
            #processed_textS = kullaniciVektorS(ialanlari)

            documents=makale_collection.find()
            """
            for article_vector in documents:#burada birinde 300 digerinde 700 olmasindan dolayi hata cikitor
                user_vector=user_data.get(kullaniciVektorF)
                similarity_score = cosine_similarity(article_vector,user_vector)
                print("ft Cosine Similarity Score:", similarity_score)

                user_vector1=user_data.get(kullaniciVektorS)
                similarity_score = cosine_similarity(article_vector,user_vector1)
                print("sb Cosine Similarity Score:", similarity_score)    
            """

            return render(request, 'dashboard.html', {'user_data': user_data})
        else:
            # Kullanici verileri bulunamadiysa hata mesaji goster
            messages.error(request, 'Kullanici verileri bulunamadi.')
            return redirect('home')
    else:
        # Kullanici oturumu kapali ise ana sayfaya yonlendir
        return redirect('home')


def userLogin(request):
    form = AuthenticationForm()
    #makaleKayit()    #bu kısım tum makaleler yuklenikten sonra yoruma alinmali
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = users_collection.find_one({'email': email})
            if user is not None:  # Kullanici bulunduysa
                stored_password = user.get('password')
                if password == stored_password:
                    # Sifre dogru, kullanici oturumunu baslat
                    print("User found and password is correct.")
                    # Oturumu baslatmak icin gerekli adimlari gerceklestirin
                    request.session['user_email'] = email
                    return redirect('dashboard')  # veya baska bir sayfaya yonlendirin
                else:
                    # Sifre yanlis
                    print("User found but password is incorrect.")
                    messages.error(request, 'Gecersiz kullanici adi veya parola.')
            else:
                print("User not found with email:", email)
                messages.error(request, 'Kullanici bulunamadi.')
        except Exception as e:
            print("An error occurred while processing the request:", e)
            messages.error(request, 'Hata olustu.')
    return render(request, 'login.html', {'form': form})


def userLogout(request):
    logout(request)  # Kullanicinin oturumunu sonlandir
    return redirect('home')  # veya baska bir sayfaya yonlendir


def updatefullname(request):
    if request.method == 'POST':
        new_fullname = request.POST.get('info')
        if new_fullname:
            # Yeni adi veritabaninda guncelle
            try:
                user_email = request.session['user_email']
                users_collection.update_one({'email': user_email}, {'$set': {'fullname': new_fullname}})
                messages.success(request, 'Adiniz basariyla guncellendi.')
                return redirect('dashboard')
            except Exception as e:
                print("An error occurred while updating fullname:", e)
                messages.error(request, 'Ad guncelleme islemi sonrasinda bir hata olustu.')
        else:
            messages.error(request, 'Lutfen yeni adinizi girin.')
    
    return redirect('dashboard')  # POST istegi olmadiginda veya hata oldugunda kullaniciya yonlendir


def updateInterestAreas(request):
    if 'user_email' in request.session:
        # Kullanici oturumu acik ise dashboard sayfasini goster
        user_data = users_collection.find_one({'email': request.session['user_email']})
        if user_data:
            return render(request, 'updateInterestAreas.html', {'user_data': user_data})
        else:
            # Kullanici verileri bulunamadiysa hata mesaji goster
            messages.error(request, 'Kullanıcı verileri bulunamadı.')
            return redirect('home')
    else:
        # Kullanici oturumu kapali ise ana sayfaya yonlendir
        return redirect('home')


def updateInterestAreasForm(request):
    if request.method == 'POST':
        ilgi_alanlari = request.POST.getlist('ilgi_alanlari')
        if ilgi_alanlari:
            # Guncellenen ilgi alanlarini veritabaninda kaydet
            try:
                user_email = request.session.get('user_email')
                if user_email:  # Kullanici oturumu var mi kontrol et
                    users_collection.update_one({'email': user_email}, {'$set': {'ilgi_alanlari': ilgi_alanlari}})
                    messages.success(request, 'ilgi alanlari basariyla guncellendi.')
                else:
                    messages.error(request, 'Kullanici oturumu bulunamadı.')
            except Exception as e:
                print("ilgi alanlari guncelleme sonrasinda bir hata olustu:", e)
                messages.error(request, 'ilgi alanlari guncelleme islemi sonrasinda bir hata olustu.')
        else:
            messages.error(request, 'Lutfen en az bir ilgi alanı seçin.')
    
    return redirect('dashboard')

# Metin on isleme fonksiyonu
#bu kisimda makalelerinde on isleme adimi yapilacak
def preprocess_text(text):
    #print("PREPROCESS İŞLEMİ")
    text= " ".join(text)
    text = text.lower()# kucuk harfe donusturuldu
    text = text.translate(str.maketrans('', '', string.punctuation))# noktalama isaretleri
    words = word_tokenize(text)#kelimeler ayrildi
    #print("a1")
    stop_words = set(stopwords.words('english'))
    words = [word for word in words if word not in stop_words]
    #print("a1")
    stemmer = SnowballStemmer("english")
    words = [stemmer.stem(word) for word in words]
    #print("PREPROCES WORD")
    return words

def kullaniciVektorF(ilgiAlanlari):#fasttext

    preprocessed_profile = " ".join(preprocess_text(ilgiAlanlari))    # Metin on isleme adimlari uygulandi
    user_vector = fasttext_model.get_sentence_vector(preprocessed_profile)
    #print("kullanici vektor:", user_vector)

    return user_vector


def kullaniciVektorS(ilgiAlanlari):#SCIBERT
    preprocessed_profile = " ".join(preprocess_text(ilgiAlanlari))    # Metin on isleme adimlari uygulandi

    scibert_tokens = scibert_tokenizer.encode(preprocessed_profile, return_tensors="pt", padding=True, truncation=True)
    scibert_output = scibert_model(scibert_tokens)
    user_vector = scibert_output.pooler_output.detach().numpy()[0]
    #print("scibertvektor",user_vector)
    
    return user_vector

#EKLEME: makalekayit alırken anahtar kelimelerde eklenmeli
def makaleKayit():#makaleleri vektorleriyle birlikte mognodbye kayit eder
    dosya_yolu="Inspec/docsutf8/"
    dosya_yolu2="Inspec/keys/"
    makale_collection = db['articles']  # Koleksiyon adi

    for dosya_adi in os.listdir(dosya_yolu):
        if dosya_adi.endswith(".txt"): 
            
            with open(os.path.join(dosya_yolu, dosya_adi), 'r', encoding='utf-8',errors='ignore') as dosya:
                makale_icerik = dosya.read()
                #print(makale_icerik)
                print(dosya_adi)
                ft_makale_vektor=makaleVektorF(makale_icerik).tolist()
                sb_makale_vektor=makaleVektorS(makale_icerik).tolist()
                makale_verisi = {
                    "baslik": dosya_adi,
                    "icerik": makale_icerik,
                    "fasttext":ft_makale_vektor,
                    "scibert":sb_makale_vektor
                }
                makale_collection.insert_one(makale_verisi)
    print("Makaleler MongoDB'ye basariyla eklendi.")


def makaleVektorS(makale):#SCIBERT
    preprocessed_article = " ".join(preprocess_text(makale))    # Metin on isleme adimlari uygulandi

    scibert_tokens = scibert_tokenizer.encode(preprocessed_article, return_tensors="pt", padding=True, truncation=True)
    scibert_output = scibert_model(scibert_tokens)
    makale_vector = scibert_output.pooler_output.detach().numpy()[0]
    #print("scibertvektor",makale_vector)
    return makale_vector

def makaleVektorF(makale):#fasttext
    preprocessed_article = " ".join(preprocess_text(makale))    # Metin on isleme adimlari uygulandi
    makale_vector = fasttext_model.get_sentence_vector(preprocessed_article)
    #print("fast vektor:", makale_vector)

    return makale_vector

def cosine_similarity(makaleVektoru, kullaniciVektoru):
    dot_product = np.dot(makaleVektoru, kullaniciVektoru)
    norm1 = np.linalg.norm(makaleVektoru)
    norm2 = np.linalg.norm(kullaniciVektoru)
    similarity = dot_product / (norm1 * norm2)
    return similarity
