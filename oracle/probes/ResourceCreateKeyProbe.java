import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDTilingPattern;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType2;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;
import org.apache.pdfbox.pdmodel.common.PDStream;

/**
 * Pins org.apache.pdfbox.pdmodel.PDResources resource-key allocation
 * (createKey). Each line is "label=key" so the pytest oracle can assert the
 * generated key sequence is byte-identical to Apache PDFBox 3.0.7.
 *
 * createKey seeds the counter to the sub-dictionary's keySet().size() and
 * pre-increments, then walks upward past collisions — i.e. 1-based, NOT the
 * smallest-free-integer.
 */
public class ResourceCreateKeyProbe {
    public static void main(String[] args) {
        // First / second / third key on empty resources (ExtGState).
        PDResources r1 = new PDResources();
        System.out.println("extgstate_first=" + r1.add(new PDExtendedGraphicsState()).getName());
        System.out.println("extgstate_second=" + r1.add(new PDExtendedGraphicsState()).getName());
        System.out.println("extgstate_third=" + r1.add(new PDExtendedGraphicsState()).getName());

        // Pre-existing /gs1 collision (size 1) → seed 1, ++ → gs2.
        PDResources r2 = new PDResources();
        COSDictionary e2 = new COSDictionary();
        e2.setItem(COSName.getPDFName("gs1"), new COSDictionary());
        r2.getCOSObject().setItem(COSName.EXT_G_STATE, e2);
        System.out.println("collision_gs1=" + r2.add(new PDExtendedGraphicsState()).getName());

        // Pre-existing /gs5 only (size 1) → gs2 (NOT the lowest free gs1).
        PDResources r3 = new PDResources();
        COSDictionary e3 = new COSDictionary();
        e3.setItem(COSName.getPDFName("gs5"), new COSDictionary());
        r3.getCOSObject().setItem(COSName.EXT_G_STATE, e3);
        System.out.println("seed_from_size_gs5=" + r3.add(new PDExtendedGraphicsState()).getName());

        // Gap {F0,F2} (size 2) → seed 2, ++ → F3 (no gap fill).
        PDResources r4 = new PDResources();
        COSDictionary f4 = new COSDictionary();
        f4.setItem(COSName.getPDFName("F0"), new COSDictionary());
        f4.setItem(COSName.getPDFName("F2"), new COSDictionary());
        r4.getCOSObject().setItem(COSName.FONT, f4);
        System.out.println("gap_F0_F2=" + r4.add(stdFont()).getName());

        // First key per prefix on empty resources.
        System.out.println("prefix_extgstate=" + new PDResources().add(new PDExtendedGraphicsState()).getName());
        System.out.println("prefix_shading=" + new PDResources().add(new PDShadingType2(new COSDictionary())).getName());
        System.out.println("prefix_colorspace=" + new PDResources().add((PDColorSpace) PDDeviceRGB.INSTANCE).getName());
        System.out.println("prefix_pattern=" + new PDResources().add(new PDTilingPattern()).getName());
        System.out.println("prefix_properties=" + new PDResources().add(plainPropertyList()).getName());
        System.out.println("prefix_ocg=" + new PDResources().add(new PDOptionalContentGroup("L")).getName());
        System.out.println("prefix_font=" + new PDResources().add(stdFont()).getName());
        System.out.println("prefix_form=" + new PDResources().add(new PDFormXObject(new PDStream(new org.apache.pdfbox.pdmodel.PDDocument()))).getName());

        // Two distinct resources in the SAME sub-dict: second seeds from
        // size 1 → index 2 (regardless of prefix).
        PDResources r5 = new PDResources();
        String oc = r5.add(new PDOptionalContentGroup("L")).getName();
        String prop = r5.add(plainPropertyList()).getName();
        System.out.println("mixed_properties_ocg=" + oc);
        System.out.println("mixed_properties_plain=" + prop);
    }

    private static org.apache.pdfbox.pdmodel.font.PDType1Font stdFont() {
        return new org.apache.pdfbox.pdmodel.font.PDType1Font(
            org.apache.pdfbox.pdmodel.font.Standard14Fonts.FontName.HELVETICA);
    }

    private static PDPropertyList plainPropertyList() {
        return PDPropertyList.create(new COSDictionary());
    }
}
