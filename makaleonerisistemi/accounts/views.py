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


logger = logging.getLogger(__name__)

# MongoDB'ye bağlan
client = MongoClient('localhost', 27017)
db = client['amosdb']  # MongoDB veritabanı adı
users_collection = db['users']  # Kullanıcı koleksiyonu
#nltk.download('punkt')# bunu bir kere indirmeliyiz
#nltk.download('stopwords')# bunu bir kere indirmeliyiz

def userRegister(request):
    if request.method == 'POST':
        # Formdan gelen verileri al
        fullname = request.POST.get('fullname')
        email = request.POST.get('email')
        password = request.POST.get('password')
        ilgi_alanlari = request.POST.getlist('ilgi_alanlari')  # Çoklu seçimleri al
        
        # Veri kontrolü yap
        if fullname and email and password and ilgi_alanlari:
            # MongoDB'ye kaydet
            users_collection = db['users']  # Koleksiyon adı
            user_data = {
                'fullname': fullname,
                'email': email,
                'password': password,
                'ilgi_alanlari': ilgi_alanlari
            }
            users_collection.insert_one(user_data)
            
            # Başarılı kayıt olduktan sonra başka bir sayfaya yönlendir
            return redirect('login')  # 'home' isimli URL'ye yönlendir
        else:
            # Hata mesajı göster
            messages.error(request, 'Lütfen tüm alanları doldurun.')
    
    return render(request, 'register.html')  # GET request olduğunda register.html sayfasını göster

def home(request):
    return render(request, "index.html")


def dashboard(request):
    if 'user_email' in request.session:
        
        # Kullanıcı oturumu açık ise dashboard sayfasını göster
        user_data = users_collection.find_one({'email': request.session['user_email']})
        if user_data:
            ialanlari=str(user_data.get('ilgi_alanlari'))
            processed_text = preprocess_text(ialanlari+"  dataing, cries, studies ")
            print("processed_text: ",processed_text)
            return render(request, 'dashboard.html', {'user_data': user_data})
        else:
            # Kullanıcı verileri bulunamadıysa hata mesajı göster
            messages.error(request, 'Kullanıcı verileri bulunamadı.')
            return redirect('home')
    else:
        # Kullanıcı oturumu kapalı ise ana sayfaya yönlendir
        return redirect('home')


def userLogin(request):
    form = AuthenticationForm()
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = users_collection.find_one({'email': email})
            if user is not None:  # Kullanıcı bulunduysa
                stored_password = user.get('password')
                if password == stored_password:
                    # Şifre doğru, kullanıcı oturumunu başlat
                    print("User found and password is correct.")
                    # Oturumu başlatmak için gerekli adımları gerçekleştirin
                    request.session['user_email'] = email
                    return redirect('dashboard')  # veya başka bir sayfaya yönlendirin
                else:
                    # Şifre yanlış
                    print("User found but password is incorrect.")
                    messages.error(request, 'Geçersiz kullanıcı adı veya parola.')
            else:
                print("User not found with email:", email)
                messages.error(request, 'Kullanıcı bulunamadı.')
        except Exception as e:
            print("An error occurred while processing the request:", e)
            messages.error(request, 'Hata oluştu.')

    return render(request, 'login.html', {'form': form})


def userLogout(request):
    logout(request)  # Kullanıcının oturumunu sonlandır
    return redirect('home')  # veya başka bir sayfaya yönlendir


def updatefullname(request):
    if request.method == 'POST':
        new_fullname = request.POST.get('info')
        if new_fullname:
            # Yeni adı veritabanında güncelle
            try:
                user_email = request.session['user_email']
                users_collection.update_one({'email': user_email}, {'$set': {'fullname': new_fullname}})
                messages.success(request, 'Adınız başarıyla güncellendi.')
                return redirect('dashboard')
            except Exception as e:
                print("An error occurred while updating fullname:", e)
                messages.error(request, 'Ad güncelleme işlemi sırasında bir hata oluştu.')
        else:
            messages.error(request, 'Lütfen yeni adınızı girin.')
    
    return redirect('dashboard')  # POST isteği olmadığında veya hata olduğunda kullanıcıyı yönlendir


def updateInterestAreas(request):
    if 'user_email' in request.session:
        # Kullanıcı oturumu açık ise dashboard sayfasını göster
        user_data = users_collection.find_one({'email': request.session['user_email']})
        if user_data:
            return render(request, 'updateInterestAreas.html', {'user_data': user_data})
        else:
            # Kullanıcı verileri bulunamadıysa hata mesajı göster
            messages.error(request, 'Kullanıcı verileri bulunamadı.')
            return redirect('home')
    else:
        # Kullanıcı oturumu kapalı ise ana sayfaya yönlendir
        return redirect('home')


def updateInterestAreasForm(request):
    if request.method == 'POST':
        ilgi_alanlari = request.POST.getlist('ilgi_alanlari')
        if ilgi_alanlari:
            # Güncellenen ilgi alanlarını veritabanında kaydet
            try:
                user_email = request.session.get('user_email')
                if user_email:  # Kullanıcı oturumu var mı kontrol et
                    users_collection.update_one({'email': user_email}, {'$set': {'ilgi_alanlari': ilgi_alanlari}})
                    messages.success(request, 'İlgi alanları başarıyla güncellendi.')
                else:
                    messages.error(request, 'Kullanıcı oturumu bulunamadı.')
            except Exception as e:
                print("İlgi alanları güncelleme sırasında bir hata oluştu:", e)
                messages.error(request, 'İlgi alanları güncelleme işlemi sırasında bir hata oluştu.')
        else:
            messages.error(request, 'Lütfen en az bir ilgi alanı seçin.')
    
    return redirect('dashboard')

# Metin ön işleme fonksiyonu
def preprocess_text(text):
    print("PREPROCESS İŞLEMİ")
    text = text.lower()# kucuk harfe donusturuldu
    text = text.translate(str.maketrans('', '', string.punctuation))# noktalama isaretleri
    words = word_tokenize(text)#kelimeler ayrildi
    print("a1")
    stop_words = set(stopwords.words('english'))
    words = [word for word in words if word not in stop_words]
    print("a1")
    stemmer = SnowballStemmer("english")
    words = [stemmer.stem(word) for word in words]
    print("PREPROCES WORD")
    return words
