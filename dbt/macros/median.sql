{% macro median(column) %}{{ return(adapter.dispatch('median')(column)) }}{% endmacro %}

{% macro default__median(column) %}median({{ column }}){% endmacro %}

{% macro bigquery__median(column) %}approx_quantiles({{ column }}, 2)[offset(1)]{% endmacro %}
