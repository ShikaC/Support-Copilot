package com.cyagent.supportcopilot.analysis;

import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

import org.springframework.stereotype.Component;

import com.cyagent.supportcopilot.analysis.AnalysisResponse.Classification;
import com.cyagent.supportcopilot.analysis.AnalysisResponse.Decision;
import com.cyagent.supportcopilot.analysis.AnalysisResponse.Retrieval;
import com.cyagent.supportcopilot.analysis.AnalysisResponse.RetrievalHit;
import com.cyagent.supportcopilot.analysis.AnalysisResponse.SuggestedReply;
import com.cyagent.supportcopilot.analysis.AnalysisResponse.Usage;
import com.cyagent.supportcopilot.analysis.AnalysisResponse.WorkflowStep;
import com.cyagent.supportcopilot.ticket.Ticket;

@Component
public class MockAnalysisFactory {

	public AnalysisResponse create(Ticket ticket, String mode) {
		var category = ticket.getCategory();
		var lowEvidence = "DATA_RECOVERY".equals(category);
		var serviceFallback = "fallback".equals(mode);
		var fallback = lowEvidence || serviceFallback;
		var escalation = fallback
			|| List.of("BILLING", "PRIVACY", "ACCOUNT_ACCESS", "DATA_RECOVERY").contains(category);
		var hits = lowEvidence ? List.<RetrievalHit>of() : hitsFor(category);
		var effectiveMode = fallback ? "fallback" : mode;

		return new AnalysisResponse(
			"run_" + compactUuid(),
			"trace_" + compactUuid(),
			fallback ? "FALLBACK" : "SUCCEEDED",
			effectiveMode,
			"configured-chat-model",
			"ticket-analysis-v1",
			new Classification(
				intentFor(category),
				category,
				ticket.getPriority(),
				"LOW".equals(ticket.getPriority()) ? "NEUTRAL" : "NEGATIVE",
				lowEvidence ? 0.42 : serviceFallback ? Math.min(0.5, confidenceFor(category)) : confidenceFor(category),
				reasonFor(category)
			),
			workflow(lowEvidence, serviceFallback, hits.size()),
			new Retrieval(queryFor(ticket), hits),
			replyFor(category, lowEvidence, serviceFallback),
			new Decision(
				escalation,
				escalationReason(category, lowEvidence, serviceFallback)
			),
			new Usage(1268, 224, lowEvidence ? 912 : 1684),
			Instant.now()
		);
	}

	private List<WorkflowStep> workflow(boolean lowEvidence, boolean serviceFallback, int hitCount) {
		var retrievalDescription = lowEvidence
			? "未找到满足阈值的有效证据"
			: serviceFallback
				? "AI 服务不可用，采用本地兜底资料"
				: "重排序后采用 " + hitCount + " 条证据";
		var generationDescription = serviceFallback
			? "生成待人工复核的降级回复"
			: lowEvidence
				? "生成谨慎回复并保留不确定性"
				: "已根据证据生成回复草稿";
		var riskDescription = serviceFallback
			? "AI 服务不可用，转入人工复核"
			: lowEvidence
				? "证据不足，转入人工复核"
				: "规则检查完成";
		return List.of(
			step("normalize", "内容预处理", "语言识别与敏感字段标记完成", 38L),
			step("classify", "工单理解", "类别、优先级与情绪识别完成", 472L),
			step("retrieve", "知识检索", retrievalDescription, 326L),
			step("generate", "回复生成", generationDescription, 812L),
			step("risk", "风险检查", riskDescription, 36L)
		);
	}

	private WorkflowStep step(String id, String name, String description, Long durationMs) {
		return new WorkflowStep(id, name, description, "complete", durationMs);
	}

	private List<RetrievalHit> hitsFor(String category) {
		if ("ACCOUNT_ACCESS".equals(category)) {
			return List.of(
				hit("account-01", "账号访问故障排查手册", "3.1 企业 SSO",
					"企业 SSO 用户应先确认身份提供商状态与域名配置。若普通密码入口被禁用，不应要求用户重置平台密码。", 0.953, 1),
				hit("account-02", "账号访问故障排查手册", "1.4 连续验证失败",
					"连续五次验证失败会触发保护锁定，管理员可在确认身份后执行一次性解锁。", 0.842, 2)
			);
		}

		if ("BILLING".equals(category)) {
			return List.of(
				hit("billing-07", "账单异常与退款处理政策", "3.2 重复扣款",
					"确认相同账期、金额与支付方式出现两笔已完成交易后，应创建支付核验记录。核验前不得承诺退款到账时间。", 0.946, 1),
				hit("payment-04", "支付争议处理手册", "2.1 核验所需信息",
					"支付核验需要订单号、扣款日期、金额和支付渠道，重复扣款应转交账务支持组复核。", 0.918, 2)
			);
		}

		return List.of(hit(
			"general-01",
			"客户支持标准处理手册",
			"2.3 信息确认",
			"客服应先确认客户问题、影响范围和期望结果，再根据问题类别选择处理流程。",
			0.831,
			1
		));
	}

	private RetrievalHit hit(String id, String title, String section, String content, double score, int rank) {
		return new RetrievalHit(
			"chunk-" + id,
			"doc-" + id.split("-")[0],
			title,
			section,
			content,
			"kb://" + id,
			"HYBRID",
			rank,
			Math.max(0, score - 0.08),
			rank,
			score,
			true
		);
	}

	private SuggestedReply replyFor(String category, boolean lowEvidence, boolean serviceFallback) {
		if (serviceFallback) {
			return new SuggestedReply(
				"AI 分析服务当前不可用。系统已保留工单信息，请客服根据知识依据人工确认分类与回复内容。",
				List.of(),
				List.of("AI 服务不可用，本次为降级结果，必须人工复核。")
			);
		}

		if (lowEvidence) {
			return new SuggestedReply(
				"您好，我们需要由数据支持团队确认该项目是否仍在可恢复范围内。当前知识库没有足够依据承诺恢复结果，请提供项目名称和大致删除日期。",
				List.of(),
				List.of("证据不足，禁止承诺可以恢复。")
			);
		}

		if ("BILLING".equals(category)) {
			return new SuggestedReply(
				"您好，我们已收到您反馈的重复扣款问题。请补充对应订单号、扣款日期、金额和支付渠道。收到信息后，我们会转交账务支持组复核。在交易核验完成前，我们暂时无法确认退款结果与到账时间。[1][2]",
				List.of("账单异常与退款处理政策 §3.2", "支付争议处理手册 §2.1"),
				List.of("支付争议需要人工核验，不可直接承诺退款。")
			);
		}

		return new SuggestedReply(
			"您好，我们已经收到您的问题，并完成了初步分类。支持人员会根据知识库处理流程核对相关信息，并在当前工单中继续回复您。[1]",
			List.of("客户支持标准处理手册 §2.3"),
			List.of()
		);
	}

	private String intentFor(String category) {
		return switch (category) {
			case "BILLING" -> "duplicate_charge";
			case "ACCOUNT_ACCESS" -> "sso_login_issue";
			case "INVOICE" -> "invoice_correction";
			case "DATA_EXPORT" -> "export_job_stalled";
			case "SUBSCRIPTION" -> "plan_capacity_question";
			case "PRIVACY" -> "data_subject_request";
			case "TECHNICAL" -> "technical_error";
			case "DATA_RECOVERY" -> "deleted_project_recovery";
			default -> "general_support_request";
		};
	}

	private double confidenceFor(String category) {
		return switch (category) {
			case "PRIVACY" -> 0.95;
			case "ACCOUNT_ACCESS" -> 0.93;
			case "BILLING" -> 0.88;
			case "SUBSCRIPTION" -> 0.84;
			default -> 0.86;
		};
	}

	private String reasonFor(String category) {
		return switch (category) {
			case "BILLING" -> "涉及重复扣款，需要账务核验，且客户已明确表达时效诉求。";
			case "ACCOUNT_ACCESS" -> "企业登录能力受阻，影响范围较大，需要身份认证团队关注。";
			case "PRIVACY" -> "包含数据导出与删除请求，必须经过身份和授权核验。";
			case "DATA_RECOVERY" -> "知识库未找到覆盖当前保留期的有效资料，需要人工确认。";
			case "SUBSCRIPTION" -> "用户正在评估套餐能力与计费方式，属于低风险咨询。";
			default -> "已依据问题内容和影响范围生成初步分类，等待客服确认。";
		};
	}

	private String queryFor(Ticket ticket) {
		return switch (ticket.getCategory()) {
			case "BILLING" -> "重复扣款 支付核验 退款处理流程";
			case "ACCOUNT_ACCESS" -> "企业 SSO 登录循环 身份提供商 域名配置";
			case "PRIVACY" -> "离职员工 数据导出 删除请求 授权核验";
			case "DATA_RECOVERY" -> "删除项目 备份恢复 保留期";
			default -> ticket.getSubject().toLowerCase(Locale.ROOT);
		};
	}

	private String escalationReason(String category, boolean lowEvidence, boolean serviceFallback) {
		if (serviceFallback) {
			return "AI 服务不可用，本次结果为降级结果，必须人工复核。";
		}
		if (lowEvidence) {
			return "检索无有效证据，必须人工确认资料与处理边界。";
		}
		return switch (category) {
			case "BILLING" -> "支付争议属于高风险类别，必须由账务支持组核验交易记录。";
			case "PRIVACY" -> "隐私请求必须由合规专员审核。";
			case "ACCOUNT_ACCESS" -> "企业账号访问受阻，需要身份认证值班组确认。";
			default -> "当前问题风险较低，可由一线客服审核回复。";
		};
	}

	private String compactUuid() {
		return UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase(Locale.ROOT);
	}
}
