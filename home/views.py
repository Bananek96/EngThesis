from django.shortcuts import render
from django.http import HttpResponse

def index_pl(request):
    return render(request, 'home/index_pl.html')

def index_en(request):
    return render(request, 'home/index_en.html')