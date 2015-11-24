﻿from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.core.urlresolvers import reverse_lazy, reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone

from .models import Listing, ListingPicture
from .forms import UserForm, ListingForm, ListingPictureForm
from django.forms import modelformset_factory

from django.views.generic import View
from django.views.generic.edit import UpdateView, DeleteView
from django.views.generic.detail import SingleObjectMixin

import re

from django.db.models import Q

# This function takes a formset, cleans it, enumerates it, and saves the corresponding object to the database. 
# This function is not a view; just providing a service.
def savePictureFormToDB(pictureFormSet, listing):
	# Get data from the form
	cleaned_data = pictureFormSet.cleaned_data

	# For each picture the user uploads, create a corresponding ListingPicture object
	for index, pic in enumerate(pictureFormSet):
		if cleaned_data[index] == {}:
			break
		imgPath = cleaned_data[index]['picture']
		print(imgPath)
		picture = ListingPicture.objects.create(picture=imgPath, picture_id=listing)
		picture.save()	
	return		

# Defining a generic editing views for handling when the user wants to edit/update their listing.
class ListingUpdate(UpdateView):
	model = Listing
	template_name = 'blog/listing_update.html'
	pk_url_kwarg = 'listing_id'
	fields = ['title', 'price', 'text']

	# Here we are instantiating a formset with ListingPictureForm.
	ListingPictureFormSet = modelformset_factory(ListingPicture, form=ListingPictureForm, extra=5, max_num=5)
	pictureFormSet = None

	# Overriding UpdateView's post() method in order to provide our own implementation.
	def post(self, request, listing_id):
		# Initializing formset with existing pictures from the listing (queryset).
		pictureFormSet = self.ListingPictureFormSet(request.POST, request.FILES, queryset=ListingPicture.objects.filter(picture_id=listing_id))

		# Set the object instance in case user cancels their delete request.
		# Must be called self.object since we are overriding the UpdateView's self.object.
		self.object = get_object_or_404(Listing, pk=listing_id)
		if request.user == self.object.author:
			# Save updated picture form to database if there's been a change
			if pictureFormSet.has_changed():
				savePictureFormToDB(pictureFormSet, self.object)
			return super(ListingUpdate, self).post(request, listing_id)
		else:
			# Return to main page if user tries perform an unauthorized action.
			return HttpResponseRedirect("/")

	# Overriding UpdateView's get_context_data() method in order to include the formset in the template.
	def get_context_data(self, **kwargs):
		# Get context object from UpdateView.
		context = super(ListingUpdate, self).get_context_data(**kwargs)
		try:
			# Build a picture formset based on the listing the user is editing. 
			pictureFormSet = self.ListingPictureFormSet(queryset=ListingPicture.objects.filter(picture_id=context['listing'].key))
			# Pass it to the context object so it's accessible to the template.
			# This is equivalent to render(request, <template path>, {'pictures': pictureFormSet})
			context['pictures'] = pictureFormSet
		except Exception as e:
			context['pictures'] = None
		return context

# Defining a generic delete views for handling when the user wants to delete their listing.
class ListingDelete(DeleteView):
	model = Listing
	pk_url_kwarg = 'listing_id'
	success_url = reverse_lazy('listing_list')

	# Overriding DeleteView's post() in order to provide our own implementation.
	def post(self, request, listing_id):
		# Set the object instance in case user cancels their delete request.
		# Must be called self.object since we are overriding the DeleteView's self.object.
		self.object = get_object_or_404(Listing, pk=listing_id)
		if request.user == self.object.author:
			# "Cancel" refers to the tag <input name="Cancel" ...> from the template listing_confirm_delete.html
			if "Cancel" in request.POST:
				url = self.get_success_url()
				return HttpResponseRedirect(url)
			else:
				return super(ListingDelete, self).post(request, listing_id)
		else:
			# Return to main page if user tries perform an unauthorized action.
			return HttpResponseRedirect("/")

# Defining the base view here. Basic homepage.
def base(request):
	# We return a rendered index.html
	return render(request, 'blog/index.html', {})

# This is for registering a new account on the site.
def register(request):
	if request.method == "POST":
		form = UserForm(request.POST)
		if form.is_valid():
			username, password = form.cleaned_data['username'], form.cleaned_data['password']
			user = User.objects.create_user(username=username, password=password)
			user.is_active = True
			user.save()
			new_user = authenticate(username=username, password=password)
			login(request, new_user)
			return HttpResponseRedirect("/listing_list")
	else:
		form = UserForm()

	return render(request, 'blog/register.html', {'form': form})

# When the user clicks the "Browse" button in the navbar.
def listing_list(request):
	listings = Listing.objects.filter(published_date__lte=timezone.now()).order_by('published_date')
	return render(request, 'blog/listing_list.html', {'listings': listings})

# For viewing a blog listing individually. We load the primary key of the listing from the database.
# Refer to the <a> tag inside listing_list.html 
def listing_detail(request, listing_id):
	listing = get_object_or_404(Listing, pk=listing_id)
	pictures = ListingPicture.objects.filter(picture_id=listing_id)
	return render(request, 'blog/listing_detail.html', {'listing': listing, 'pictures': pictures})

# For creating a new listing.
def listing_new(request):
	ListingPictureFormSet = modelformset_factory(ListingPicture, form=ListingPictureForm, extra=5, max_num=5)

	if request.method == "POST":
		form = ListingForm(request.POST)
		pictureFormSet = ListingPictureFormSet(request.POST, request.FILES, queryset=ListingPicture.objects.none())

		if form.is_valid():
			title, text, price = form.cleaned_data['title'], form.cleaned_data['text'], form.cleaned_data['price']
			listing = Listing.objects.create(author=request.user, title=title, text=text, price=price)
			listing.publish()

			if pictureFormSet.is_valid():
				savePictureFormToDB(pictureFormSet, listing)

			return HttpResponseRedirect("/listing_list")
	else:
		form = ListingForm()
		pictureFormSet = ListingPictureFormSet(queryset=ListingPicture.objects.none())

	return render(request, 'blog/listing_new.html', {'form': form, 'pictureFormSet': pictureFormSet})



#the new search implementation

def normalize_query(query_string,
                    findterms=re.compile(r'"([^"]+)"|(\S+)').findall,
                    normspace=re.compile(r'\s{2,}').sub):
    ''' Splits the query string in invidual keywords, getting rid of unecessary spaces
        and grouping quoted words together.
        Example:
        
        >>> normalize_query('  some random  words "with   quotes  " and   spaces')
        ['some', 'random', 'words', 'with quotes', 'and', 'spaces']
    
    '''
    return [normspace(' ', (t[0] or t[1]).strip()) for t in findterms(query_string)] 

def get_query(query_string, search_fields):
    ''' Returns a query, that is a combination of Q objects. That combination
        aims to search keywords within a model by testing the given search fields.
    
    '''
    query = None # Query to search for every search term        
    terms = normalize_query(query_string)
    for term in terms:
        or_query = None # Query to search for a given term in each field
        for field_name in search_fields:
            q = Q(**{"%s__icontains" % field_name: term})
            if or_query is None:
                or_query = q
            else:
                or_query = or_query | q
        if query is None:
            query = or_query
        else:
            query = query & or_query
    return query



    def search(request):
    query_string = ''
    found_entries = None
    if ('q' in request.GET) and request.GET['q'].strip():
        query_string = request.GET['q']
        
        entry_query = get_query(query_string, ['title', 'body',])
        
        found_entries = Entry.objects.filter(entry_query).order_by('-pub_date')

    return render_to_response('search/search_results.html',
                          { 'query_string': query_string, 'found_entries': found_entries },
                          context_instance=RequestContext(request))