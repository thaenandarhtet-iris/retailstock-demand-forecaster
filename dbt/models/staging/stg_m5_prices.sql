select item_id, wm_yr_wk, sell_price
from {{ source('raw', 'm5_prices') }}
