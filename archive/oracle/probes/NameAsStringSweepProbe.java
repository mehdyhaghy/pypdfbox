import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.pdmodel.font.PDCIDFontType2;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.PDType3Font;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceNAttributes;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationMarkup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderEffectDictionary;

/**
 * Consolidated differential probe for the {@code getName} vs
 * {@code getNameAsString} parity-bug class (pypdfbox wave 1556).
 *
 * <p>For each accessor that pypdfbox switched from {@code get_name(KEY)} to
 * {@code get_name_as_string(KEY)} after disassembly confirmed Apache PDFBox
 * 3.0.7 reads the same key with {@code getNameAsString}, this probe stores the
 * relevant key as a {@link COSString} (the value that {@code getName} silently
 * drops to the default) and projects the accessor result.
 *
 * <p>Usage: {@code java NameAsStringSweepProbe <accessor>}. Prints one line:
 * {@code value=<result>} ({@code null} stands in for a Java {@code null}).
 */
public final class NameAsStringSweepProbe {

    static String nz(String s) {
        return s == null ? "null" : s;
    }

    static void put(COSDictionary dict, COSName key, String value) {
        dict.setItem(key, new COSString(value));
    }

    public static void main(String[] args) throws Exception {
        String accessor = args[0];
        String result;
        switch (accessor) {
            case "encryption_filter": {
                COSDictionary d = new COSDictionary();
                put(d, COSName.FILTER, "MyFilter");
                result = new PDEncryption(d).getFilter();
                break;
            }
            case "encryption_sub_filter": {
                COSDictionary d = new COSDictionary();
                put(d, COSName.SUB_FILTER, "MySub");
                result = new PDEncryption(d).getSubFilter();
                break;
            }
            case "font_type": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.SUBTYPE, COSName.TYPE1);
                put(d, COSName.TYPE, "Font");
                result = new PDType1Font(d).getType();
                break;
            }
            case "font_subtype": {
                COSDictionary d = new COSDictionary();
                put(d, COSName.SUBTYPE, "Type1");
                d.setItem(COSName.BASE_FONT, COSName.getPDFName("Helvetica"));
                result = new PDType1Font(d).getSubType();
                break;
            }
            case "font_base_font": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.SUBTYPE, COSName.TYPE1);
                put(d, COSName.BASE_FONT, "Helvetica");
                result = new PDType1Font(d).getName();
                break;
            }
            case "type0_base_font": {
                COSDictionary descendant = new COSDictionary();
                descendant.setItem(COSName.TYPE, COSName.FONT);
                descendant.setItem(COSName.SUBTYPE, COSName.CID_FONT_TYPE2);
                descendant.setItem(COSName.BASE_FONT,
                    COSName.getPDFName("MyComposite"));
                COSDictionary cidSystemInfo = new COSDictionary();
                cidSystemInfo.setString(COSName.getPDFName("Registry"), "Adobe");
                cidSystemInfo.setString(COSName.getPDFName("Ordering"), "Identity");
                cidSystemInfo.setInt(COSName.getPDFName("Supplement"), 0);
                descendant.setItem(COSName.CIDSYSTEMINFO, cidSystemInfo);
                org.apache.pdfbox.cos.COSArray descendants =
                    new org.apache.pdfbox.cos.COSArray();
                descendants.add(descendant);
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.TYPE, COSName.FONT);
                d.setItem(COSName.SUBTYPE, COSName.TYPE0);
                d.setItem(COSName.ENCODING, COSName.IDENTITY_H);
                d.setItem(COSName.DESCENDANT_FONTS, descendants);
                put(d, COSName.BASE_FONT, "MyComposite");
                result = new PDType0Font(d).getBaseFont();
                break;
            }
            case "cid_base_font": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.SUBTYPE, COSName.CID_FONT_TYPE2);
                put(d, COSName.BASE_FONT, "MyCIDFont");
                result = new PDCIDFontType2(d, null).getBaseFont();
                break;
            }
            case "type3_name": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.SUBTYPE, COSName.TYPE3);
                put(d, COSName.NAME, "MyType3");
                result = new PDType3Font(d).getName();
                break;
            }
            case "font_stretch": {
                COSDictionary d = new COSDictionary();
                put(d, COSName.FONT_STRETCH, "Condensed");
                result = new org.apache.pdfbox.pdmodel.font.PDFontDescriptor(d)
                    .getFontStretch();
                break;
            }
            case "structure_type": {
                COSDictionary d = new COSDictionary();
                put(d, COSName.S, "Sect");
                result = new PDStructureElement(d).getStructureType();
                break;
            }
            case "structure_node_type": {
                COSDictionary d = new COSDictionary();
                put(d, COSName.TYPE, "StructElem");
                result = new PDStructureElement(d).getType();
                break;
            }
            case "markup_reply_type": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.SUBTYPE, COSName.getPDFName("Text"));
                put(d, COSName.RT, "Group");
                result = new PDAnnotationMarkup(d).getReplyType();
                break;
            }
            case "markup_intent": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.SUBTYPE, COSName.getPDFName("Text"));
                put(d, COSName.IT, "LineArrow");
                result = new PDAnnotationMarkup(d).getIntent();
                break;
            }
            case "freetext_line_ending": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.SUBTYPE, COSName.getPDFName("FreeText"));
                put(d, COSName.LE, "OpenArrow");
                result = new org.apache.pdfbox.pdmodel.interactive.annotation
                    .PDAnnotationFreeText(d).getLineEndingStyle();
                break;
            }
            case "line_caption_positioning": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.SUBTYPE, COSName.getPDFName("Line"));
                put(d, COSName.CP, "Top");
                result = new PDAnnotationLine(d).getCaptionPositioning();
                break;
            }
            case "border_effect_style": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.S, new COSString("C"));
                result = new PDBorderEffectDictionary(d).getStyle();
                break;
            }
            case "device_n_is_n_channel": {
                COSDictionary d = new COSDictionary();
                put(d, COSName.SUBTYPE, "NChannel");
                result = Boolean.toString(new PDDeviceNAttributes(d).isNChannel());
                break;
            }
            default:
                throw new IllegalArgumentException("unknown accessor: " + accessor);
        }
        System.out.println("value=" + nz(result));
    }
}
