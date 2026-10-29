from django.contrib.sitemaps import Sitemap

from apps.listings.models import Listing


class ListingSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Listing.objects.public()

    def lastmod(self, obj):
        return obj.updated_at
