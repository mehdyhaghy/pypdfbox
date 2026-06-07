import java.io.File;
import java.io.PrintStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSound;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe for SOUND annotation appearance generation — the
 * OPERAND-LEVEL ``/AP`` result.
 *
 * Drives {@code PDSoundAppearanceHandler.generateNormalAppearance()} (invoked
 * via {@code PDAnnotationSound.constructAppearances(doc)}) for each supported
 * icon name — {@code Speaker} / {@code Mic} — plus a missing-/Name annotation
 * and an unknown-/Name annotation, with and without a stroke colour.
 *
 * Apache PDFBox 3.0.7's {@code PDSoundAppearanceHandler} is an unimplemented
 * stub: all three {@code generate*Appearance} methods are
 * {@code // TODO to be implemented} no-ops, so {@code constructAppearances}
 * routes through the handler but writes NO appearance stream. This probe pins
 * that no-op contract (every record reports {@code NOAP}) so pypdfbox's
 * faithful stub cannot silently start emitting an appearance and diverge.
 *
 * Two modes:
 *
 *   java ... SoundAnnotationIconProbe write out.pdf
 *   java ... SoundAnnotationIconProbe read out.pdf
 */
public final class SoundAnnotationIconProbe {
    // Upstream PDAnnotationSound has no icon-name accessor; /Name is the
    // ``Speaker``/``Mic`` icon per PDF 32000-1:2008 §12.5.6.16, set on the COS
    // dict directly. The default (absent /Name) icon is ``Speaker``.
    private static final String DEFAULT_NAME = "Speaker";
    private static final String[] NAMES = {"Speaker", "Mic"};

    private static void setName(PDAnnotationSound ann, String name) {
        ann.getCOSObject().setName(COSName.NAME, name);
    }

    private static String resolvedName(PDAnnotationSound ann) {
        String name = ann.getCOSObject().getNameAsString(COSName.NAME);
        return name != null ? name : DEFAULT_NAME;
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        File file = new File(args[1]);
        if ("write".equals(mode)) {
            write(file);
        } else {
            read(file);
        }
    }

    private static void write(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.A4);
            doc.addPage(page);
            float y = 750;
            // 1) every supported icon name, no colour.
            for (String name : NAMES) {
                PDAnnotationSound ann = new PDAnnotationSound();
                ann.setRectangle(new PDRectangle(50, y, 30, 30));
                setName(ann, name);
                ann.constructAppearances(doc);
                page.getAnnotations().add(ann);
                y -= 45;
            }
            // 2) colour set on Speaker — would exercise the stroke-colour path
            //    if the handler were implemented; pins it still NOAP.
            float[] red = {1f, 0f, 0f};
            PDAnnotationSound coloured = new PDAnnotationSound();
            coloured.setRectangle(new PDRectangle(50, y, 30, 30));
            setName(coloured, DEFAULT_NAME);
            coloured.setColor(new PDColor(red, PDDeviceRGB.INSTANCE));
            coloured.constructAppearances(doc);
            page.getAnnotations().add(coloured);
            y -= 45;
            // 3) /Name absent — getName() defaults to "Speaker".
            PDAnnotationSound missing = new PDAnnotationSound();
            missing.setRectangle(new PDRectangle(50, y, 30, 30));
            missing.constructAppearances(doc);
            page.getAnnotations().add(missing);
            y -= 45;
            // 4) unknown /Name.
            PDAnnotationSound unknown = new PDAnnotationSound();
            unknown.setRectangle(new PDRectangle(50, y, 30, 30));
            setName(unknown, "DefinitelyNotAStandardIcon");
            unknown.constructAppearances(doc);
            page.getAnnotations().add(unknown);
            doc.save(file);
        }
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            for (PDPage page : doc.getPages()) {
                for (PDAnnotation annot : page.getAnnotations()) {
                    emit(sb, annot);
                }
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, PDAnnotation annot) throws Exception {
        sb.append("ANNOT ").append(resolvedName((PDAnnotationSound) annot)).append('\n');
        COSBase rawName = annot.getCOSObject().getDictionaryObject(COSName.NAME);
        sb.append("RAWNAME ")
          .append(rawName instanceof COSName ? ((COSName) rawName).getName() : "__absent__")
          .append('\n');
        sb.append("RECT ").append(rectStr(annot.getRectangle())).append('\n');

        PDAppearanceStream stream = normalStream(annot);
        if (stream == null) {
            sb.append("NOAP\nEND\n");
            return;
        }
        sb.append("BBOX ").append(rectStr(stream.getBBox())).append('\n');
        sb.append("HASSTREAM\nEND\n");
    }

    private static String rectStr(PDRectangle r) {
        if (r == null) {
            return "none";
        }
        return canon(r.getLowerLeftX()) + ","
                + canon(r.getLowerLeftY()) + ","
                + canon(r.getUpperRightX()) + ","
                + canon(r.getUpperRightY());
    }

    private static String canon(double value) {
        BigDecimal bd = new BigDecimal(Double.toString(value))
                .setScale(3, RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0") || s.isEmpty()) {
            s = "0";
        }
        return s;
    }

    private static PDAppearanceStream normalStream(PDAnnotation annot) {
        PDAppearanceDictionary ap = annot.getAppearance();
        if (ap == null) {
            return null;
        }
        PDAppearanceEntry normal = ap.getNormalAppearance();
        if (normal == null || normal.isSubDictionary()) {
            return null;
        }
        return normal.getAppearanceStream();
    }
}
