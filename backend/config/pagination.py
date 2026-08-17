from rest_framework.pagination import PageNumberPagination


class OseorPagination(PageNumberPagination):
    """
    Pagination standard OSEOR : 25 résultats par défaut.
    Le frontend peut demander jusqu'à 500 via ?page_size=N
    (utilisé par le calendrier global des salles).
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 500
