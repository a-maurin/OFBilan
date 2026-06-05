import pytest
from reportlab.platypus import Paragraph, Spacer, Image as RLImage, KeepTogether
from bilans.common.pdf_report_builder import PDFReportBuilder
from reportlab.lib.styles import getSampleStyleSheet
import tempfile
from pathlib import Path

def test_no_orphan_titles_in_keeptogether():
    """
    Test guard pour éviter qu'un bloc contenant uniquement [Titre, Spacer]
    ne soit enfermé dans un KeepTogether, ce qui annule le keepWithNext
    et provoque des titres orphelins en bas de page.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test.pdf"
        builder = PDFReportBuilder(pdf_path, header_title="Test")
        
        styles = getSampleStyleSheet()
        title_para = Paragraph("Titre test", styles["Heading1"])
        spacer = Spacer(1, 10)
        from unittest.mock import MagicMock
        img = MagicMock(spec=RLImage)
        
        block = [title_para, spacer, img]
        
        # Test leading chunk length logic
        # Should return 2 (title + spacer) so the image is not included
        chunk_len = builder._leading_title_chunk_len(block)
        assert chunk_len == 2
        
        prefix = block[:chunk_len]
        
        # Le test doit s'assurer que si on appelle _append_with_pending avec keep_together=True,
        # le préfixe (qui n'a QUE le titre et l'espace) ne finit pas bêtement dans un KeepTogether
        # sinon on perd l'effet keepWithNext !
        
        def mock_story_append(item):
            # Guard: on ne devrait jamais ajouter un KeepTogether qui ne contient
            # aucun "vrai" contenu de fond (texte ou tableau), c'est-à-dire 
            # seulement des Paragraph (titres) et Spacer.
            if isinstance(item, KeepTogether):
                has_content = False
                for inner_item in item._flowables:
                    # Dans notre cas d'usage, si le prefix est juste [titre, spacer], 
                    # il ne devrait pas être encapsulé.
                    pass
                # Vérification simplifiée: si item correspond exactement à [Titre, Spacer]
                if len(item._flowables) == 2 and isinstance(item._flowables[0], Paragraph) and isinstance(item._flowables[1], Spacer):
                    pytest.fail("Un [Titre, Spacer] a été enfermé dans un KeepTogether, ce qui crée un titre orphelin.")
                    
        builder.story.append = mock_story_append
        builder._append_with_pending(block, keep_together=True)
