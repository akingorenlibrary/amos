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
from bson import ObjectId

logger = logging.getLogger(__name__)

# MongoDB'ye baglan
client = MongoClient('localhost', 27017)
db = client['amosdb']  # MongoDB veritabani adi
users_collection = db['users']  # Kullanici koleksiyonu
makale_collection = db['articles']  # Makale koleksiyonu



#nltk.download('punkt')# bunu bir kere indirmeliyiz
#nltk.download('stopwords')# bunu bir kere indirmeliyiz

#fasttext.util.download_model("en", if_exists="ignore")# bu model iï¿½in bir kere indirdikten sonra kapatilacak
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
            messages.error(request, 'Lutfen tum alanlari doldurun.')
    
    return render(request, 'register.html')  # GET request oldugunda register.html sayfasini goster

def home(request):
    if 'user_email' not in request.session:
        return redirect('login')
    return render(request, "index.html")

def dashboard(request):
    if 'user_email' in request.session:
        
        # Kullanici oturumu acik ise dashboard sayfasini goster
        user_data = users_collection.find_one({'email': request.session['user_email']})
        if user_data:
            ialanlari = str(user_data.get('ilgi_alanlari'))
            arama=str(user_data.get('searchKeys'))
            if arama:
                ialanlari = f"{ialanlari}, {arama}"

            print("ialan+arama:-",ialanlari)
            #processed_textF = kullaniciVektorF(ialanlari)
            #processed_textS = kullaniciVektorS(ialanlari)
            documents = makale_collection.find()
            user_vector = kullaniciVektorF(ialanlari)
            user_vector1 = kullaniciVektorS(ialanlari)
            similarity_scores = []
            similarity_scores2 = []
            similarity_id = []
            similarity_id2 = []

            if user_vector is not None and user_vector1 is not None:
                for article_vector in documents:
                    ft = article_vector.get("fasttext", [])
                    similarity_score = cosine_similarity(ft, user_vector)
                    similarity_scores.append((article_vector.get("_id"), similarity_score))
                    #print("ft Cosine Similarity Score - " + str(article_vector.get("baslik")) + ": ", similarity_score)

                    st = article_vector.get("scibert", [])
                    similarity_score2 = cosine_similarity(st, user_vector1)
                    similarity_scores2.append((article_vector.get("_id"), similarity_score2))
                    #print("sb Cosine Similarity Score - " + str(article_vector.get("baslik")) + ": ", similarity_score2)   
                
                top_5_scores_with_ids = get_top_5_similarity_scores_with_ids(similarity_scores)
                top_5_scores_with_ids2 = get_top_5_similarity_scores_with_ids(similarity_scores2)
                print("top_5_scores_with_ids: ", top_5_scores_with_ids)
                print("top_5_scores_with_ids2: ", top_5_scores_with_ids2)
                for fso in top_5_scores_with_ids:
                    similarity_id.append(fso[0])
                for fso in top_5_scores_with_ids2:
                    similarity_id2.append(fso[0])
                #print(similarity_id)
                    
                # Kullanýcý verilerini güncelle
                users_collection.update_one({'_id': user_data['_id']}, {'$set': {'f_advantages': similarity_id}})
                users_collection.update_one({'_id': user_data['_id']}, {'$set': {'s_advantages': similarity_id2}})

                # Kullanýcýnýn ilgili makalelerini al
                f_advantages = user_data.get('f_advantages', [])
                s_advantages = user_data.get('s_advantages', [])

                # Ýlgili makaleleri çek
                f_advantages_articles = makale_collection.find({'_id': {'$in': f_advantages}})
                s_advantages_articles = makale_collection.find({'_id': {'$in': s_advantages}})

                f_advantages_data = []
                for article in f_advantages_articles:
                    article_data = {
                        "kimlik": str(article["_id"]),
                        "baslik": article["baslik"],
                        "icerik": article["icerik"],
                        "key_icerik": article["key_icerik"]
                    }
                    # Makale verisini listeye ekle
                    f_advantages_data.append(article_data)

            return render(request, 'dashboard.html', {'user_data': user_data, "f_advantages_data":f_advantages_data, "s_advantages_articles":s_advantages_articles})   
    
        else:
            # Kullanici verileri bulunamadiysa hata mesaji goster
            messages.error(request, 'Kullanici verileri bulunamadi.')
            return redirect('home')
    else:
        # Kullanici oturumu kapali ise ana sayfaya yonlendir
        return redirect('home')
        
def search(request):
    query = request.GET.get('query', '')
    search_option = request.GET.get('search_option', '')
    print("search_option: ",search_option)

    if search_option == 'baslik':
        articles = makale_collection.find({'baslik': {'$regex': query, '$options': 'i'}})
    elif search_option == 'key':
        articles = makale_collection.find({'key_icerik': {'$regex': query, '$options': 'i'}})
    elif search_option == 'baslikAndKey':
        articles = makale_collection.find({
            '$or': [
                {'baslik': {'$regex': query, '$options': 'i'}},
                {'key_icerik': {'$regex': query, '$options': 'i'}}
            ]
        })
    else:
        articles = makale_collection.find({'baslik': {'$regex': query, '$options': 'i'}})

    f_advantages_data = []
    for article in articles:
        article_data = {
            "kimlik": str(article["_id"]),
            "baslik": article["baslik"],
            "icerik": article["icerik"],
            "key_icerik": article["key_icerik"]
        }
        f_advantages_data.append(article_data)

    return render(request, 'index.html', {'results': f_advantages_data})


def get_top_5_similarity_scores_with_ids(similarity_scores):
    # similarity_scores listesini benzerlik skorlarýna göre sýrala
    sorted_similarity_scores = sorted(similarity_scores, key=lambda x: x[1], reverse=True)

    # En yüksek 5 benzerlik skorunu seç
    top_5_similarity_scores = sorted_similarity_scores[:5]

    # Her bir benzerlik skorunun karþýsýna makale ID'sini ekleyerek iki boyutlu bir dizi oluþtur
    top_5_similarity_scores_with_ids = [(article_id, similarity_score) for article_id, similarity_score in top_5_similarity_scores]

    return top_5_similarity_scores_with_ids

def articleDetail(request, id):
    obj_id = ObjectId(id)
    article = makale_collection.find_one({"_id": obj_id})
    user_email = request.session['user_email']
    users_collection.update_one(
        {'email': user_email},
        {'$addToSet': {'searchKeys': article.get('key_icerik')}}
    )
    return render(request, 'articleDetail.html', {'article': article})

def userLogin(request):
    form = AuthenticationForm()
    #makaleKayit()    #bu kÄ±sÄ±m tum makaleler yuklenikten sonra yoruma alinmali
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
            messages.error(request, 'KullanÄ±cÄ± verileri bulunamadÄ±.')
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
                    messages.error(request, 'Kullanici oturumu bulunamadÄ±.')
            except Exception as e:
                print("ilgi alanlari guncelleme sonrasinda bir hata olustu:", e)
                messages.error(request, 'ilgi alanlari guncelleme islemi sonrasinda bir hata olustu.')
        else:
            messages.error(request, 'Lutfen en az bir ilgi alanÄ± seÃ§in.')
    
    return redirect('dashboard')

# Metin on isleme fonksiyonu
#bu kisimda makalelerinde on isleme adimi yapilacak
def preprocess_text(text):
    #print("PREPROCESS Ä°ÅžLEMÄ°")
    #text= " ".join(text)  #bu hatali
    text = text.replace('\n', ' ').replace('\t', ' ')
    text = text.replace("\\n", ' ').replace("\\t", ' ')

    text = text.lower()# kucuk harfe donusturuldu
    #print("lower==",text)
    text = text.translate(str.maketrans('', '', string.punctuation))# noktalama isaretleri
    #print("noktalama==",text)
    words = word_tokenize(text)#kelimeler ayrildi
    #print("token==",words)
    #print("a1")
    stop_words = set(stopwords.words('english'))
    
    words = [word for word in words if word not in stop_words]
    #print("a1")
    stemmer = SnowballStemmer("english")
    words = [stemmer.stem(word) for word in words]
    #print("PREPROCES WORD")
    #print("stopword==",words)

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

#EKLEME: makalekayit alÄ±rken anahtar kelimelerde eklenmeli
def makaleKayit():#makaleleri vektorleriyle birlikte mognodbye kayit eder
    dosya_yolu="Inspec/docsutf8/"
    dosya_yolu2="Inspec/keys/"
    makale_collection = db['articles']  # Koleksiyon adi
    index=0
    for dosya_adi in os.listdir(dosya_yolu):
        index+=1
        print(dosya_adi)
        if index==51:
            break
        if dosya_adi.endswith(".txt"): 
            
            with open(os.path.join(dosya_yolu, dosya_adi), 'r', encoding='utf-8',errors='ignore') as dosya:
                makale_icerik = dosya.read()
                #print(makale_icerik)
                print(dosya_adi)
                ft_makale_vektor=makaleVektorF(makale_icerik).tolist()
                sb_makale_vektor=makaleVektorS(makale_icerik).tolist()
                print("b1") 

            dosya_adi = dosya_adi[:-4]+".key"

            with open(os.path.join(dosya_yolu2, dosya_adi), 'r', encoding='utf-8',errors='ignore') as dosya2:
                            key_icerik = dosya2.read()
                            print("key_icerik: ",key_icerik)
                            print("dosya_adi2: ",dosya_adi)
                            ft_key_vektor=makaleVektorF(key_icerik).tolist()
                            sb_key_vektor=makaleVektorS(key_icerik).tolist()
                        
                            print("key MongoDB'ye basariyla eklendi.")

                            makale_verisi = {
                                "baslik": dosya_adi,
                                "icerik": makale_icerik,
                                "fasttext":ft_makale_vektor,
                                "scibert":sb_makale_vektor,
                                "key_icerik":key_icerik,
                                "ft_key_vektor":ft_key_vektor,
                                "sb_key_vektor":sb_key_vektor,
                            }
                            makale_collection.insert_one(makale_verisi)            
    print("Makaleler MongoDB'ye basariyla eklendi.")


    


def makaleVektorS(makale):#SCIBERT
    preprocessed_article = " ".join(preprocess_text(makale))    # Metin on isleme adimlari uygulandi

    scibert_tokens = scibert_tokenizer.encode(preprocessed_article, return_tensors="pt", padding=True, max_length=512, truncation=True)
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