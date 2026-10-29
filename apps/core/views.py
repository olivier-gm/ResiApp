from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.listings.models import Listing
from apps.locations.models import FederalEntity


@require_GET
def home(request):
    listings = Listing.objects.public().with_card_data().filter(operation="rent")[:3]
    categories = [
        ("apartment", "Apartamentos", "▦"),
        ("house", "Casas", "⌂"),
        ("annex", "Anexos", "▤"),
        ("room", "Habitaciones", "▥"),
    ]
    return render(
        request,
        "core/home.html",
        {"states": FederalEntity.objects.all(), "listings": listings, "categories": categories},
    )


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
def robots(request):
    return HttpResponse(
        f"User-agent: *\nDisallow: /panel/\nDisallow: /cuenta/\nDisallow: /admin/\nSitemap: {settings.PUBLIC_BASE_URL}/sitemap.xml\n",
        content_type="text/plain",
    )


@require_GET
def legal(request, page):
    content = {
        "privacidad": (
            "Privacidad",
            [
                "Usamos los datos de tu cuenta para administrar publicaciones, favoritos, consultas y visitas. El nombre público y la información de anuncios aprobados son visibles; las conversaciones están limitadas a sus participantes.",
                "El correo, teléfono y dirección exacta no aparecen en el anuncio público. Si habilitas contacto por WhatsApp, ese número será visible al usar el enlace. Las fotos se procesan para eliminar metadatos de ubicación.",
                "Puedes modificar tus preferencias y solicitar la eliminación de la cuenta desde tu perfil. El equipo debe revisar la retención de conversaciones, denuncias y copias de respaldo antes de completar la solicitud.",
                "La infraestructura utiliza PostgreSQL de Supabase y almacenamiento de imágenes Cloudflare R2. Las sesiones usan cookies necesarias para acceder de forma segura. No se incluyen rastreadores publicitarios.",
            ],
        ),
        "terminos": (
            "Condiciones de uso",
            [
                "Publica únicamente inmuebles que estés autorizado a ofrecer y proporciona información precisa, fotografías propias y costos completos. Propietario o asesor es una declaración del anunciante.",
                "ResiVe conecta interesados y anunciantes. Las consultas y visitas no reservan viviendas ni cobran dinero. Cada operación requiere que las partes verifiquen identidad, condiciones, documentos y autorización para ofrecer el inmueble.",
                "El equipo puede solicitar cambios, retirar anuncios o suspender cuentas por contenido engañoso, acoso o uso indebido. Puedes solicitar revisión mediante una denuncia o la información de tu cuenta.",
            ],
        ),
        "ayuda": (
            "Ayuda y seguridad",
            [
                "Busca por estado, ciudad y presupuesto. Guarda tus favoritos y consulta al anunciante desde el detalle. Para publicar o contactar debes verificar tu correo.",
                "Antes de entregar dinero, visita la vivienda y comprueba quién está autorizado a ofrecerla. Desconfía de solicitudes urgentes, enlaces desconocidos y pagos para acceder a una visita.",
                "Usa Denunciar en el anuncio o en un mensaje para avisar al equipo. Puedes bloquear nuevos mensajes de un contacto desde el hilo. Consulta las respuestas y motivos de revisión en tu panel.",
            ],
        ),
    }
    if page not in content:
        raise Http404
    title, paragraphs = content[page]
    return render(request, "core/legal.html", {"title": title, "paragraphs": paragraphs})
