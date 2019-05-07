import json

from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from rest_framework.generics import ListAPIView, RetrieveAPIView

from apps.package.models import Package
from apps.searchv2.builders import build_index
from apps.searchv2.forms import SearchForm
from apps.searchv2.models import SearchV2
from apps.searchv2.utils import clean_title, remove_prefix


@login_required
def build_search(request, template_name="searchv2/build_results.html"):

    if not request.user.is_superuser:
        return HttpResponseForbidden()

    results = []
    if request.method == "POST":
        results = build_index()

    return render(request, template_name, {"results": results})


def search_function(q):
    """ TODO - make generic title searches have lower weight """

    items = []
    if q:
        items = SearchV2.objects.filter(
            Q(clean_title__startswith=clean_title(remove_prefix(q)))
            | Q(title__icontains=q)
            | Q(title_no_prefix__startswith=q.lower())
            | Q(slug__startswith=q.lower())
            | Q(slug_no_prefix__startswith=q.lower())
        )
        # grids    = Grid.objects.filter(Q(title__icontains=q) | Q(description__icontains=q))
    return items


def search(request, template_name="searchv2/search.html"):
    """
    Searches in Grids and Packages
    """
    q = request.GET.get("q", "")

    if "/" in q:
        lst = q.split("/")
        try:
            if lst[-1]:
                q = lst[-1]
            else:
                q = lst[-2]
        except IndexError:
            pass
    try:
        package = Package.objects.get(title=q)
        url = reverse("package", args=[package.slug.lower()])
        return HttpResponseRedirect(url)
    except Package.DoesNotExist:
        pass
    except Package.MultipleObjectsReturned:
        pass

    try:
        package = Package.objects.get(slug=q)
        url = reverse("package", args=[package.slug.lower()])
        return HttpResponseRedirect(url)
    except Package.DoesNotExist:
        pass
    except Package.MultipleObjectsReturned:
        pass

    form = SearchForm(request.GET or None)

    return render(
        request,
        template_name,
        {
            "items": search_function(q),
            "form": form,
            "max_weight": SearchV2.objects.all().aggregate(Max("weight"))["weight__max"],
        },
    )


def search_packages_autocomplete(request):
    """
    Searches in Packages
    """
    q = request.GET.get("term", "")
    if q:
        objects = search_function(q)[:15]
        objects = objects.values_list("title", flat=True)
        json_response = json.dumps(list(objects))
    else:
        json_response = json.dumps([])

    return HttpResponse(json_response, mimetype="text/javascript")


class SearchListAPIView(ListAPIView):
    model = SearchV2
    paginate_by = 20

    def get_queryset(self):
        q = self.request.GET.get("q", "")
        return search_function(q)


class SearchDetailAPIView(RetrieveAPIView):
    model = SearchV2
