package com.cyagent.supportcopilot.knowledge;

import java.util.Comparator;
import java.util.List;
import java.util.Locale;

import org.springframework.stereotype.Service;

@Service
public class KnowledgeService {

	private final List<KnowledgeHit> catalog = List.of(
		new KnowledgeHit("chunk-billing-07", "账单异常与退款处理政策", "3.2 重复扣款",
			"确认相同账期、金额与支付方式出现两笔交易后，应创建支付核验记录。", "POLICY", 0.946),
		new KnowledgeHit("chunk-payment-04", "支付争议处理手册", "2.1 核验所需信息",
			"核验需要订单号、扣款日期、金额和支付渠道。", "RUNBOOK", 0.918),
		new KnowledgeHit("chunk-account-01", "账号访问故障排查手册", "3.1 企业 SSO",
			"企业 SSO 用户应先确认身份提供商状态与域名配置。", "RUNBOOK", 0.953),
		new KnowledgeHit("chunk-privacy-03", "数据主体请求处理规范", "4.2 删除请求",
			"删除请求必须完成身份、授权和数据范围核验。", "POLICY", 0.939),
		new KnowledgeHit("chunk-sync-2047", "桌面客户端同步错误码", "SYNC-2047",
			"SYNC-2047 通常与代理网络或客户端版本不兼容有关。", "FAQ", 0.927)
	);

	public List<KnowledgeHit> search(String query, int topK) {
		var normalized = query == null ? "" : query.toLowerCase(Locale.ROOT);
		return catalog.stream()
			.map(hit -> hit.withScore(score(hit, normalized)))
			.sorted(Comparator.comparingDouble(KnowledgeHit::score).reversed())
			.limit(Math.max(1, Math.min(topK, 10)))
			.toList();
	}

	private double score(KnowledgeHit hit, String query) {
		if (query.isBlank()) return hit.score();
		var text = String.join(" ", hit.documentTitle(), hit.section(), hit.content()).toLowerCase(Locale.ROOT);
		var matches = query.codePoints().filter(codePoint -> text.indexOf(codePoint) >= 0).count();
		return Math.min(0.99, 0.55 + matches * 0.015);
	}

	public record KnowledgeHit(
		String chunkId,
		String documentTitle,
		String section,
		String content,
		String documentType,
		double score
	) {
		KnowledgeHit withScore(double newScore) {
			return new KnowledgeHit(chunkId, documentTitle, section, content, documentType, newScore);
		}
	}
}
