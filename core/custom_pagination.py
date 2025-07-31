from rest_framework.pagination import PageNumberPagination

from core.constants import CUSTOM_PAGINATION_PAGE_SIZE, CUSTOM_MAX_PAGE_SIZE


class CustomPaginationClass(PageNumberPagination):
    page_size = CUSTOM_PAGINATION_PAGE_SIZE
    page_size_query_param = 'page_size'
    max_page_size = CUSTOM_MAX_PAGE_SIZE
