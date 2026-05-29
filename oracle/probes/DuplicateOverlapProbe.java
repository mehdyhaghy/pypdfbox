import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for PDFTextStripper.setSuppressDuplicateOverlappingText.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> DuplicateOverlapProbe build  out.pdf
 *   java -cp <pdfbox-app.jar>:<build> DuplicateOverlapProbe extract in.pdf
 *
 * "build" writes a fake-bold / drop-shadow fixture: the word "Hello" is
 * painted, then re-painted after a tiny Td offset (a fraction of a glyph
 * advance), so the coincident glyphs are duplicates of one another. This
 * is the classic technique PDFTextStripper's default
 * setSuppressDuplicateOverlappingText(true) must collapse.
 *
 * "extract" emits two framed sections, UTF-8 to stdout:
 *   <<<ON ... ON>>>   text with suppression on  (upstream default)
 *   <<<OFF ... OFF>>> text with suppression off (toggle parity)
 */
public final class DuplicateOverlapProbe {
    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final String mode = args[0];
        if ("build".equals(mode)) {
            build(new File(args[1]));
            return;
        }
        try (PDDocument doc = Loader.loadPDF(new File(args[1]))) {
            PDFTextStripper on = new PDFTextStripper();
            on.setSortByPosition(true);
            // default is true, set explicitly for clarity.
            on.setSuppressDuplicateOverlappingText(true);
            out.print("<<<ON\n");
            out.print(on.getText(doc));
            out.print("ON>>>\n");
        }
        try (PDDocument doc = Loader.loadPDF(new File(args[1]))) {
            PDFTextStripper off = new PDFTextStripper();
            off.setSortByPosition(true);
            off.setSuppressDuplicateOverlappingText(false);
            out.print("<<<OFF\n");
            out.print(off.getText(doc));
            out.print("OFF>>>\n");
        }
    }

    private static void build(File target) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.LETTER);
            doc.addPage(page);
            PDType1Font helv = new PDType1Font(Standard14Fonts.FontName.HELVETICA);
            try (PDPageContentStream cs =
                    new PDPageContentStream(doc, page)) {
                // First paint of "Hello" at (72, 700).
                cs.beginText();
                cs.setFont(helv, 24);
                cs.newLineAtOffset(72, 700);
                cs.showText("Hello");
                cs.endText();
                // Second paint of the SAME word, offset by a tiny fraction
                // of a glyph advance (fake-bold / drop-shadow). 0.4 pt at
                // 24 pt is far below a glyph width, so each second glyph
                // coincides with its original.
                cs.beginText();
                cs.setFont(helv, 24);
                cs.newLineAtOffset(72.4f, 700.2f);
                cs.showText("Hello");
                cs.endText();
                // A genuine second word that must NOT be suppressed.
                cs.beginText();
                cs.setFont(helv, 24);
                cs.newLineAtOffset(72, 660);
                cs.showText("World");
                cs.endText();
            }
            doc.save(target);
        }
    }
}
