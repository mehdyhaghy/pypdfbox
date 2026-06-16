import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;

/**
 * Live oracle probe for PDPageContentStream RESOURCE-NAME allocation + reuse.
 *
 * Unlike ResourceCreateKeyProbe (which pokes PDResources.add directly), this
 * drives the *content stream writer* end-to-end so the projection captures the
 * names actually emitted into the content stream (the operand of Tf / Do / gs /
 * BDC) AND the final /Resources sub-dict keys. Fuzz angles:
 *
 *  - setFont twice with the SAME font object  -> one /Font key reused, one key.
 *  - setFont with two DIFFERENT fonts         -> two distinct /Font keys.
 *  - drawImage SAME image twice               -> one /XObject key reused.
 *  - drawImage two DIFFERENT images           -> two distinct /XObject keys.
 *  - setGraphicsStateParameters same / diff   -> /ExtGState gs reuse.
 *  - beginMarkedContent with a property list  -> /Properties key.
 *  - APPEND to a page that ALREADY has /Font F1 / /XObject Im1 entries: the
 *    newly-allocated name must NOT clash with the pre-existing keys (the
 *    collision-avoidance walk in createKey).
 *
 * Output (UTF-8, stdout): one "label=value" line per projection so the pytest
 * oracle can assert byte-identically. Names emitted in the stream are parsed
 * back out with PDFStreamParser and reported as the operand sequence.
 */
public final class ContentStreamResourceFuzzProbe {
    public static void main(String[] args) throws Exception {
        scenarioSameFontTwice();
        scenarioTwoFonts();
        scenarioSameImageTwice();
        scenarioTwoImages();
        scenarioSameExtGStateTwice();
        scenarioTwoExtGStates();
        scenarioMarkedContentProperties();
        scenarioAppendToExistingFont();
        scenarioAppendToExistingImage();
        scenarioMixedSequence();
    }

    private static PDType1Font helv() {
        return new PDType1Font(Standard14Fonts.FontName.HELVETICA);
    }

    private static PDType1Font times() {
        return new PDType1Font(Standard14Fonts.FontName.TIMES_ROMAN);
    }

    private static PDImageXObject solidImage(PDDocument doc, int rgb) throws Exception {
        java.awt.image.BufferedImage bi =
            new java.awt.image.BufferedImage(2, 2, java.awt.image.BufferedImage.TYPE_INT_RGB);
        for (int yy = 0; yy < 2; yy++) {
            for (int xx = 0; xx < 2; xx++) {
                bi.setRGB(xx, yy, rgb);
            }
        }
        return org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory.createFromImage(doc, bi);
    }

    private static PDExtendedGraphicsState gstate(float alpha) {
        PDExtendedGraphicsState gs = new PDExtendedGraphicsState();
        gs.setNonStrokingAlphaConstant(alpha);
        return gs;
    }

    /** Names emitted as content-stream operands, in order, prefixed by '/'. */
    private static List<String> emittedNames(PDPage page, PDDocument doc) throws Exception {
        List<String> names = new ArrayList<>();
        PDFStreamParser parser = new PDFStreamParser(page);
        for (Object tok : parser.parse()) {
            if (tok instanceof COSName) {
                names.add("/" + ((COSName) tok).getName());
            }
        }
        return names;
    }

    private static String keys(PDResources res, COSName kind) {
        COSDictionary cos = res.getCOSObject();
        COSDictionary sub = cos.getCOSDictionary(kind);
        if (sub == null) {
            return "<none>";
        }
        List<String> ks = new ArrayList<>();
        for (COSName k : sub.keySet()) {
            ks.add(k.getName());
        }
        java.util.Collections.sort(ks);
        return String.join(",", ks);
    }

    private static void emit(String label, Object value) {
        System.out.println(label + "=" + value);
    }

    // ---- scenarios ----

    private static void scenarioSameFontTwice() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDType1Font f = helv();
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.beginText();
                cs.setFont(f, 12);
                cs.setFont(f, 14);
                cs.endText();
            }
            emit("same_font_twice.font_keys", keys(page.getResources(), COSName.FONT));
        }
    }

    private static void scenarioTwoFonts() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.beginText();
                cs.setFont(helv(), 12);
                cs.setFont(times(), 14);
                cs.endText();
            }
            emit("two_fonts.font_keys", keys(page.getResources(), COSName.FONT));
        }
    }

    private static void scenarioSameImageTwice() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDImageXObject img = solidImage(doc, 0xFF0000);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.drawImage(img, 0, 0, 10, 10);
                cs.drawImage(img, 20, 20, 10, 10);
            }
            emit("same_image_twice.xobject_keys", keys(page.getResources(), COSName.XOBJECT));
        }
    }

    private static void scenarioTwoImages() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDImageXObject a = solidImage(doc, 0xFF0000);
            PDImageXObject b = solidImage(doc, 0x00FF00);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.drawImage(a, 0, 0, 10, 10);
                cs.drawImage(b, 20, 20, 10, 10);
            }
            emit("two_images.xobject_keys", keys(page.getResources(), COSName.XOBJECT));
        }
    }

    private static void scenarioSameExtGStateTwice() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDExtendedGraphicsState gs = gstate(0.5f);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.setGraphicsStateParameters(gs);
                cs.setGraphicsStateParameters(gs);
            }
            emit("same_gs_twice.extgstate_keys", keys(page.getResources(), COSName.EXT_G_STATE));
        }
    }

    private static void scenarioTwoExtGStates() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.setGraphicsStateParameters(gstate(0.5f));
                cs.setGraphicsStateParameters(gstate(0.25f));
            }
            emit("two_gs.extgstate_keys", keys(page.getResources(), COSName.EXT_G_STATE));
        }
    }

    private static void scenarioMarkedContentProperties() throws Exception {
        // Multi-key property list (NOT a bare MCID): upstream registers it
        // under /Resources/Properties and emits /Tag /Propn BDC.
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            COSDictionary mc = new COSDictionary();
            mc.setInt(COSName.getPDFName("MCID"), 0);
            mc.setName(COSName.getPDFName("Alt"), "extra");
            PDPropertyList props = PDPropertyList.create(mc);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.beginMarkedContent(COSName.getPDFName("Span"), props);
                cs.endMarkedContent();
            }
            emit("mc_props.properties_keys", keys(page.getResources(), COSName.PROPERTIES));
            emit("mc_props.emitted_names", emittedNames(page, doc));
        }
        // Bare MCID-only property list: upstream inlines <</MCID n>>, no entry.
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            COSDictionary mc = new COSDictionary();
            mc.setInt(COSName.getPDFName("MCID"), 0);
            PDPropertyList props = PDPropertyList.create(mc);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.beginMarkedContent(COSName.getPDFName("Span"), props);
                cs.endMarkedContent();
            }
            emit("mc_mcid_only.properties_keys", keys(page.getResources(), COSName.PROPERTIES));
        }
    }

    private static void scenarioAppendToExistingFont() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            // Pre-seed /Resources/Font with F1 mapped to an unrelated dict, so
            // the size-seeded createKey must walk past the collision.
            PDResources res = new PDResources();
            COSDictionary fontSub = new COSDictionary();
            fontSub.setItem(COSName.getPDFName("F1"), new COSDictionary());
            res.getCOSObject().setItem(COSName.FONT, fontSub);
            page.setResources(res);
            try (PDPageContentStream cs = new PDPageContentStream(
                    doc, page, PDPageContentStream.AppendMode.APPEND, false)) {
                cs.beginText();
                cs.setFont(helv(), 12);
                cs.endText();
            }
            emit("append_existing_font.font_keys", keys(page.getResources(), COSName.FONT));
        }
    }

    private static void scenarioAppendToExistingImage() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDResources res = new PDResources();
            COSDictionary xSub = new COSDictionary();
            xSub.setItem(COSName.getPDFName("Im1"), new COSDictionary());
            res.getCOSObject().setItem(COSName.XOBJECT, xSub);
            page.setResources(res);
            PDImageXObject img = solidImage(doc, 0x0000FF);
            try (PDPageContentStream cs = new PDPageContentStream(
                    doc, page, PDPageContentStream.AppendMode.APPEND, false)) {
                cs.drawImage(img, 0, 0, 10, 10);
            }
            emit("append_existing_image.xobject_keys", keys(page.getResources(), COSName.XOBJECT));
        }
    }

    private static void scenarioMixedSequence() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDType1Font f = helv();
            PDImageXObject img = solidImage(doc, 0x808080);
            PDExtendedGraphicsState gs = gstate(0.5f);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.setGraphicsStateParameters(gs);
                cs.beginText();
                cs.setFont(f, 12);
                cs.endText();
                cs.drawImage(img, 0, 0, 10, 10);
            }
            emit("mixed.font_keys", keys(page.getResources(), COSName.FONT));
            emit("mixed.xobject_keys", keys(page.getResources(), COSName.XOBJECT));
            emit("mixed.extgstate_keys", keys(page.getResources(), COSName.EXT_G_STATE));
            emit("mixed.emitted_names", emittedNames(page, doc));
        }
    }
}
