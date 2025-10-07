from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
import streamlit as st
import pandas as pd
import json

# -------------------------
# 🧱 DATA SETUP
# -------------------------
image_urls = [
    ["https://picsum.photos/id/10/800/600", "https://picsum.photos/id/20/800/600"],
    ["https://picsum.photos/id/60/800/600"],
    [
        "https://picsum.photos/id/90/800/600",
        "https://picsum.photos/id/91/800/600",
        "https://picsum.photos/id/92/800/600",
    ],
    ["https://picsum.photos/id/120/800/600", "https://picsum.photos/id/121/800/600"],
    ["https://picsum.photos/id/30/800/600"],
    ["https://picsum.photos/id/40/800/600"],
    ["https://picsum.photos/id/50/800/600", "https://picsum.photos/id/51/800/600"],
    ["https://picsum.photos/id/70/800/600"],
    ["https://picsum.photos/id/80/800/600", "https://picsum.photos/id/81/800/600"],
    ["https://picsum.photos/id/90/800/600"],
    ["https://picsum.photos/id/100/800/600", "https://picsum.photos/id/101/800/600"],
    ["https://picsum.photos/id/110/800/600"],
]

df = pd.DataFrame(
    {
        "SKU_NBR": [
            "S08231",
            "S08231",
            "S08231",
            "621158",
            "621158",
            "621158",
            "812450",
            "812450",
            "812450",
            "700321",
            "700321",
            "700321",
        ],
        "Product_Name": [
            "NYX Concealer",
            "NYX Concealer",
            "NYX Concealer",
            "EcoFresh Bottle",
            "EcoFresh Bottle",
            "EcoFresh Bottle",
            "GlowTech Lamp",
            "GlowTech Lamp",
            "GlowTech Lamp",
            "Sun&Sky Flip Flop",
            "Sun&Sky Flip Flop",
            "Sun&Sky Flip Flop",
        ],
        "Attributes": [
            "Headline",
            "Manufacturer",
            "Description",
            "Headline",
            "Manufacturer",
            "Description",
            "Headline",
            "Manufacturer",
            "Description",
            "Headline",
            "Manufacturer",
            "Description",
        ],
        "STIBO_Data": [
            "NYX Concealer Palette - Advanced Formula",
            "Advanced Color Correcting Concealer Palette with enhanced coverage",
            "Premium concealer for professional use",
            "EcoFresh Stainless Steel Water Bottle",
            "Durable and insulated bottle for hot and cold beverages",
            "Environmentally friendly reusable design",
            "GlowTech LED Desk Lamp",
            "Adjustable LED Lamp with touch control and brightness",
            "Smart desk accessory for modern workspaces",
            "Sun&Sky Women's Flip Flop",
            "Comfortable Flip Flops for beach and casual wear",
            "Soft cushioned sole and durable straps",
        ],
        "Recommended_Value": [
            "NYX Professional Makeup Color Correcting Concealer",
            "Color Correcting Concealer Palette",
            "Advanced Concealer Formula",
            "EcoFresh Thermal Bottle",
            "Insulated Stainless Steel Bottle",
            "Reusable Water Bottle",
            "GlowTech Smart LED Lamp",
            "LED Desk Lamp with Adjustable Brightness",
            "Smart Touch LED Lamp",
            "Sun&Sky Women's Flip Flop",
            "Comfort Beach Footwear",
            "Flip Flop - Premium Quality",
        ],
        "Scoring": [
            0.92,
            0.87,
            0.78,
            0.65,
            0.9,
            0.3,
            0.88,
            0.85,
            0.80,
            0.98,
            0.86,
            0.82,
        ],
        "Images": image_urls * 1,  # repeat pattern
        "Comment": [""] * 12,
    }
)

df["Images"] = df["Images"].apply(json.dumps)

# -------------------------
# 🧠 CUSTOM IMAGE SLIDER RENDERER
# -------------------------
image_slider_renderer = JsCode("""
class ImageSliderRenderer {
    init(params) {
        this.eGui = document.createElement('div');
        this.eGui.style.display = 'flex';
        this.eGui.style.alignItems = 'center';
        this.eGui.style.justifyContent = 'center';
        this.eGui.style.position = 'relative';
        this.eGui.style.width = '100%';
        this.eGui.style.height = '100px';
        this.eGui.style.overflow = 'hidden';
        this.eGui.style.borderRadius = '8px';
        this.eGui.style.backgroundColor = '#f8f8f8';

        try {
            const images = JSON.parse(params.value);
            if (!Array.isArray(images) || images.length === 0) {
                this.eGui.innerText = "No images";
                return;
            }

            let index = 0;
            const img = document.createElement('img');
            img.src = images[index];
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'cover';
            img.style.transition = 'opacity 0.3s ease';
            img.style.borderRadius = '8px';
            img.style.cursor = 'pointer';

            // Navigation buttons
            const leftBtn = document.createElement('button');
            const rightBtn = document.createElement('button');

            [leftBtn, rightBtn].forEach(btn => {
                btn.style.position = 'absolute';
                btn.style.top = '50%';
                btn.style.transform = 'translateY(-50%)';
                btn.style.backgroundColor = 'rgba(0,0,0,0.4)';
                btn.style.border = 'none';
                btn.style.color = 'white';
                btn.style.cursor = 'pointer';
                btn.style.fontSize = '16px';
                btn.style.padding = '2px 8px';
                btn.style.borderRadius = '5px';
                btn.style.transition = 'background 0.2s';
                btn.onmouseover = () => btn.style.backgroundColor = 'rgba(0,0,0,0.6)';
                btn.onmouseout = () => btn.style.backgroundColor = 'rgba(0,0,0,0.4)';
            });

            leftBtn.innerHTML = '◀';
            rightBtn.innerHTML = '▶';
            leftBtn.style.left = '5px';
            rightBtn.style.right = '5px';

            leftBtn.onclick = () => {
                index = (index - 1 + images.length) % images.length;
                img.style.opacity = 0;
                setTimeout(() => {
                    img.src = images[index];
                    img.style.opacity = 1;
                }, 200);
            };

            rightBtn.onclick = () => {
                index = (index + 1) % images.length;
                img.style.opacity = 0;
                setTimeout(() => {
                    img.src = images[index];
                    img.style.opacity = 1;
                }, 200);
            };

            // Open image in new tab on click
            img.onclick = () => {
                window.open(images[index], '_blank');
            };

            this.eGui.appendChild(img);
            if (images.length > 1) {
                this.eGui.appendChild(leftBtn);
                this.eGui.appendChild(rightBtn);
            }

        } catch (e) {
            this.eGui.innerText = "Invalid data";
        }
    }

    getGui() {
        return this.eGui;
    }
}
""")

# -------------------------
# 🎨 GRID CONFIGURATION
# -------------------------
gb = GridOptionsBuilder.from_dataframe(df)

# Default column styling
gb.configure_default_column(
    resizable=True,
    sortable=True,
    filter=True,
    wrapText=True,
    autoHeight=True,
    cellStyle={"fontFamily": "Inter, sans-serif", "fontSize": "13px"},
)

# Configure each column
gb.configure_column("SKU_NBR", headerName="SKU", width=100)
gb.configure_column("Product_Name", headerName="Product Name", width=160)
gb.configure_column("Attributes", headerName="Attribute", width=120)
gb.configure_column("STIBO_Data", headerName="STIBO Data", width=300)
gb.configure_column("Recommended_Value", headerName="Recommended Value", width=300)
gb.configure_column("Scoring", type=["numericColumn"], width=100)
gb.configure_column("Comment", editable=True, width=180)

# Image Slider column
gb.configure_column(
    "Images",
    headerName="Product Images",
    cellRenderer=image_slider_renderer,
    autoHeight=True,
    width=250,
    minWidth=180,
    maxWidth=300,
    editable=False,
)

# Pagination & selection
gb.configure_selection(
    selection_mode="multiple", use_checkbox=True, header_checkbox=True
)
gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=12)
gb.configure_grid_options(rowHeight=110, animateRows=True)

gridOptions = gb.build()

# -------------------------
# 🌈 THEME SWITCHER
# -------------------------
st.sidebar.markdown("🎨 **Choose AgGrid Theme**")
theme_choice = st.sidebar.selectbox(
    "Theme",
    ["alpine", "alpine-dark", "balham", "balham-dark", "streamlit", "material"],
    index=0,
)

# -------------------------
# 🚀 DISPLAY GRID
# -------------------------
st.markdown("## 🧩 Product Catalog with Image Slider & Attributes")

grid_response = AgGrid(
    df,
    gridOptions=gridOptions,
    theme=theme_choice,
    allow_unsafe_jscode=True,
    enable_enterprise_modules=True,
    fit_columns_on_grid_load=False,
)

st.write("✅ Selected Rows:", grid_response["selected_rows"])
st.write("📦 Total Rows Displayed:", len(grid_response["data"]))
