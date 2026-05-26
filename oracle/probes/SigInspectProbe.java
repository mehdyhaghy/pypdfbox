import java.io.File;
import java.io.PrintStream;
import java.security.Security;
import java.security.cert.X509Certificate;
import java.util.Collection;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;

import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.SignerInformation;
import org.bouncycastle.cms.SignerInformationStore;
import org.bouncycastle.cms.jcajce.JcaSimpleSignerInfoVerifierBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.util.Store;

/**
 * Live oracle probe: inspect every signature in a signed PDF.
 *
 * For each /Sig dictionary it prints a fixed-shape block to stdout:
 *   sig.<i>.subfilter=<value>
 *   sig.<i>.subject=<signer cert RFC2253 subject>
 *   sig.<i>.serial=<signer cert serial, decimal>
 *   sig.<i>.byterange=<a,b,c,d>
 *   sig.<i>.digestIntact=<true|false>
 * The digestIntact flag rebuilds the detached CMS over the bracketed
 * /ByteRange bytes (signature.getSignedContent(fileBytes)) and asks
 * BouncyCastle's SignerInformation.verify(...) whether the embedded
 * messageDigest + signer signature hold — i.e. the document was not
 * altered after signing and the signer key produced the SignerInfo.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SigInspectProbe signed.pdf
 */
public final class SigInspectProbe {

    public static void main(String[] args) throws Exception {
        Security.addProvider(new BouncyCastleProvider());
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        File file = new File(args[0]);
        byte[] fileBytes = java.nio.file.Files.readAllBytes(file.toPath());

        try (PDDocument doc = Loader.loadPDF(file)) {
            java.util.List<PDSignature> sigs = doc.getSignatureDictionaries();
            out.println("count=" + sigs.size());
            int i = 0;
            for (PDSignature sig : sigs) {
                String prefix = "sig." + i + ".";

                String subFilter = sig.getSubFilter();
                out.println(prefix + "subfilter=" + (subFilter == null ? "" : subFilter));

                int[] br = sig.getByteRange();
                StringBuilder brSb = new StringBuilder();
                if (br != null) {
                    for (int j = 0; j < br.length; j++) {
                        if (j > 0) {
                            brSb.append(',');
                        }
                        brSb.append(br[j]);
                    }
                }
                out.println(prefix + "byterange=" + brSb);

                byte[] contents = sig.getContents();
                byte[] signedContent = sig.getSignedContent(fileBytes);

                String subject = "";
                String serial = "";
                String digestIntact = "false";
                try {
                    CMSSignedData cms = new CMSSignedData(
                            new CMSProcessableByteArray(signedContent), contents);
                    Store<X509CertificateHolder> certStore = cms.getCertificates();
                    SignerInformationStore signers = cms.getSignerInfos();
                    Collection<SignerInformation> c = signers.getSigners();
                    for (SignerInformation si : c) {
                        Collection<X509CertificateHolder> matches =
                                certStore.getMatches(si.getSID());
                        if (matches.isEmpty()) {
                            continue;
                        }
                        X509CertificateHolder certHolder = matches.iterator().next();
                        X509Certificate cert = new JcaX509CertificateConverter()
                                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                .getCertificate(certHolder);
                        subject = cert.getSubjectX500Principal().getName();
                        serial = cert.getSerialNumber().toString();
                        boolean ok = si.verify(
                                new JcaSimpleSignerInfoVerifierBuilder()
                                        .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                        .build(certHolder));
                        digestIntact = Boolean.toString(ok);
                        break;
                    }
                } catch (Exception e) {
                    digestIntact = "error:" + e.getClass().getSimpleName();
                }

                out.println(prefix + "subject=" + subject);
                out.println(prefix + "serial=" + serial);
                out.println(prefix + "digestIntact=" + digestIntact);
                i++;
            }
        }
    }
}
