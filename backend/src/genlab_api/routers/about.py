"""Public product information for the About view and API clients."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..config import get_settings
from ..schemas import AboutOut

router = APIRouter(tags=["about"])


@router.get("/about", response_model=AboutOut)
def about() -> dict:
    """Return stable, public metadata about GenLab M5GP."""
    settings = get_settings()
    current_year = datetime.now(timezone.utc).year
    source_repository = "https://github.com/armandocardenasf/GenLab-m5gp"

    return {
        "product_name": "GenLab M5GP",
        "full_name": {
            "es": "GenLab M5GP: Laboratorio en Línea para Aprendizaje Automático utilizando M5GP",
            "en": "GenLab M5GP: Online Machine Learning Laboratory using M5GP",
        },
        "version": settings.app_version,
        "release_channel": settings.release_channel,
        "copyright": {
            "year": current_year,
            "holder": "Dr. Luis Armando Cardenas Florido",
            "role": {
                "es": "Diseñador y desarrollador de la herramienta",
                "en": "Tool designer and developer",
            },
            "notice": {
                "es": (
                    f"© {current_year} Dr. Luis Armando Cardenas Florido. "
                    "Diseño y desarrollo de GenLab M5GP, con el apoyo y patrocinio "
                    "del Tecnológico Nacional de México y del Instituto Tecnológico "
                    "de Ensenada."
                ),
                "en": (
                    f"© {current_year} Dr. Luis Armando Cardenas Florido. "
                    "GenLab M5GP design and development, with support and sponsorship "
                    "from Tecnológico Nacional de México and Instituto Tecnológico de "
                    "Ensenada."
                ),
            },
        },
        "supporting_institutions": [
            "Tecnológico Nacional de México",
            "Instituto Tecnológico de Ensenada",
        ],
        "acknowledgements": {
            "es": (
                "Se agradece al Tecnológico Nacional de México y al Instituto "
                "Tecnológico de Ensenada por su apoyo institucional y patrocinio "
                "para el desarrollo del proyecto GenLab M5GP."
            ),
            "en": (
                "We acknowledge Tecnológico Nacional de México and Instituto "
                "Tecnológico de Ensenada for their institutional support and "
                "sponsorship of the GenLab M5GP project."
            ),
        },
        "references": [
            {
                "name": "M5GP",
                "repository_url": "https://github.com/armandocardenasf/m5gp",
                "citation": (
                    "Cárdenas-Florido, L., Trujillo, L., Hernández, D. E., & "
                    "Muñoz-Contreras, J. M. (2024). M5GP: Parallel Multidimensional "
                    "Genetic Programming with Multidimensional Populations for "
                    "Symbolic Regression. Mathematical and Computational "
                    "Applications, 29(2), 25."
                ),
                "doi_url": "https://doi.org/10.3390/mca29020025",
            },
            {
                "name": "M5GP 2.0",
                "repository_url": "https://github.com/armandocardenasf/m5gp-2.0",
                "citation": (
                    "Cárdenas Florido, L., Trujillo, L., et al. (2026). M5GP 2.0: "
                    "Extensions and Enhancements to a Constructive Feature Induction "
                    "System Based on Genetic Programming. Expert Systems."
                ),
                "doi_url": "https://doi.org/10.1111/exsy.70356",
            },
        ],
        "source_code": {
            "repository_url": source_repository,
            "download_url": f"{source_repository}/archive/refs/heads/main.zip",
        },
        "legal": {
            "public_source": True,
            "open_source_intent": True,
            "license_name": {
                "es": "Licencia indicada en el archivo LICENSE del repositorio",
                "en": "License stated in the repository LICENSE file",
            },
            "license_url": f"{source_repository}/blob/main/LICENSE",
            "terms": {
                "es": (
                    "GenLab M5GP está concebido como software de código fuente público "
                    "y abierto. Los permisos concretos para usar, copiar, modificar y "
                    "redistribuir el software se rigen exclusivamente por el archivo "
                    "LICENSE publicado en el repositorio. La disponibilidad pública "
                    "del código no sustituye una licencia. Los componentes y "
                    "dependencias de terceros conservan sus licencias respectivas."
                ),
                "en": (
                    "GenLab M5GP is intended as publicly available, open-source "
                    "software. Specific permissions to use, copy, modify, and "
                    "redistribute the software are governed exclusively by the LICENSE "
                    "file published in the repository. Public availability of source "
                    "code does not replace a license. Third-party components and "
                    "dependencies remain subject to their respective licenses."
                ),
            },
            "disclaimer": {
                "es": (
                    "El software se proporciona para fines académicos, científicos y "
                    "de desarrollo, sin garantías adicionales a las establecidas por "
                    "la licencia aplicable. Los usuarios son responsables de validar "
                    "los resultados y de cumplir las licencias de las dependencias."
                ),
                "en": (
                    "The software is provided for academic, scientific, and development "
                    "purposes, without warranties beyond those stated in the applicable "
                    "license. Users are responsible for validating results and complying "
                    "with third-party dependency licenses."
                ),
            },
        },
    }
