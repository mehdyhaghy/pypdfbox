import java.io.PrintStream;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDNumberFormatDictionary;

/**
 * Live oracle probe for {@code PDNumberFormatDictionary} default-value and
 * accessor semantics (PDF 32000-1:2008 Table 117 — number format dictionary).
 *
 * The measurement package has had NO oracle coverage; this pins the exact
 * defaults each typed getter returns on an EMPTY dictionary (the riskiest
 * divergence surface — every getter that supplies a literal default), then the
 * round-trip values after each setter is exercised on a fresh instance.
 *
 * No arguments. Output (UTF-8, LF-terminated "key=value" lines):
 *
 *   Empty-dictionary defaults (each getter on a brand-new PDNumberFormatDictionary):
 *     empty.type=NumberFormat
 *     empty.units=<units-or-NULL>
 *     empty.conversionFactor=<float>
 *     empty.fractionalDisplay=<value-or-NULL>
 *     empty.denominator=<int>
 *     empty.fd=<bool>
 *     empty.thousandsSeparator=<value-or-NULL>
 *     empty.decimalSeparator=<value-or-NULL>
 *     empty.labelPrefixString=<value-or-NULL>
 *     empty.labelSuffixString=<value-or-NULL>
 *     empty.labelPositionToValue=<value-or-NULL>
 *
 *   Round-trip after setters:
 *     set.units=metres
 *     set.conversionFactor=<float>
 *     ... (etc)
 *
 *   COS wire form after the set pass (sorted /Key=presence list):
 *     wire.<KeyName>=present
 */
public final class NumberFormatDictionaryProbe {

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    public static void main(String[] args) {
        PrintStream out = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);

        PDNumberFormatDictionary nf = new PDNumberFormatDictionary();
        out.println("empty.type=" + nf.getType());
        out.println("empty.units=" + nz(nf.getUnits()));
        out.println("empty.conversionFactor=" + nf.getConversionFactor());
        out.println("empty.fractionalDisplay=" + nz(nf.getFractionalDisplay()));
        out.println("empty.denominator=" + nf.getDenominator());
        out.println("empty.fd=" + nf.isFD());
        out.println("empty.thousandsSeparator=" + nz(nf.getThousandsSeparator()));
        out.println("empty.decimalSeparator=" + nz(nf.getDecimalSeparator()));
        out.println("empty.labelPrefixString=" + nz(nf.getLabelPrefixString()));
        out.println("empty.labelSuffixString=" + nz(nf.getLabelSuffixString()));
        out.println("empty.labelPositionToValue=" + nz(nf.getLabelPositionToValue()));

        PDNumberFormatDictionary s = new PDNumberFormatDictionary();
        s.setUnits("metres");
        s.setConversionFactor(2.5f);
        s.setFractionalDisplay(PDNumberFormatDictionary.FRACTIONAL_DISPLAY_ROUND);
        s.setDenominator(16);
        s.setFD(true);
        s.setThousandsSeparator(".");
        s.setDecimalSeparator(",");
        s.setLabelPrefixString("[");
        s.setLabelSuffixString("]");
        s.setLabelPositionToValue(PDNumberFormatDictionary.LABEL_PREFIX_TO_VALUE);

        out.println("set.units=" + nz(s.getUnits()));
        out.println("set.conversionFactor=" + s.getConversionFactor());
        out.println("set.fractionalDisplay=" + nz(s.getFractionalDisplay()));
        out.println("set.denominator=" + s.getDenominator());
        out.println("set.fd=" + s.isFD());
        out.println("set.thousandsSeparator=" + nz(s.getThousandsSeparator()));
        out.println("set.decimalSeparator=" + nz(s.getDecimalSeparator()));
        out.println("set.labelPrefixString=" + nz(s.getLabelPrefixString()));
        out.println("set.labelSuffixString=" + nz(s.getLabelSuffixString()));
        out.println("set.labelPositionToValue=" + nz(s.getLabelPositionToValue()));

        COSDictionary cos = s.getCOSObject();
        java.util.TreeSet<String> keys = new java.util.TreeSet<>();
        for (COSName k : cos.keySet()) {
            keys.add(k.getName());
        }
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (String k : keys) {
            if (!first) {
                sb.append(",");
            }
            sb.append(k);
            first = false;
        }
        out.println("wire.keys=" + sb);

        // Setting null clears the entry (the null-clears-key contract).
        s.setUnits(null);
        out.println("clear.units.present=" + cos.containsKey(COSName.getPDFName("U")));
    }
}
