package com.cyagent.supportcopilot.config;

import java.time.Instant;
import java.util.List;

import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import com.cyagent.supportcopilot.analysis.AnalysisService;
import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@Component
public class DemoDataInitializer implements CommandLineRunner {

	private final TicketRepository ticketRepository;
	private final AnalysisService analysisService;

	public DemoDataInitializer(TicketRepository ticketRepository, AnalysisService analysisService) {
		this.ticketRepository = ticketRepository;
		this.analysisService = analysisService;
	}

	@Override
	public void run(String... args) {
		if (ticketRepository.count() > 0) {
			return;
		}

		var tickets = List.of(
			ticket("ticket-10042", "SC-10042", "WEB_FORM", "林澄", "远川供应链", "PREMIUM",
				"本月套餐出现重复扣款", "我们在 7 月账单里看到两笔相同的专业版套餐扣款，金额都是 2,899 元。财务今天需要完成月结，请尽快帮助核对。",
				"BILLING", "HIGH", "NEEDS_ESCALATION", "周岚", "2026-07-28T07:31:00Z", "2026-07-28T11:30:00Z"),
			ticket("ticket-10041", "SC-10041", "EMAIL", "沈言", "栖岸建筑设计", "ENTERPRISE",
				"企业 SSO 登录后反复跳回登录页", "今天上午开始，团队成员通过 Azure AD 登录后会再次跳回登录页面。普通账号仍然可以登录。",
				"ACCOUNT_ACCESS", "URGENT", "READY_FOR_REVIEW", "陈屿", "2026-07-28T06:58:00Z", "2026-07-28T09:45:00Z"),
			ticket("ticket-10039", "SC-10039", "CHAT", "许闻笙", "浦岚生物", "STANDARD",
				"修改已开具发票的公司抬头", "上周开具的电子发票公司名称少了上海两个字，请问能否作废重开？",
				"INVOICE", "MEDIUM", "IN_PROGRESS", "苏遥", "2026-07-28T05:44:00Z", "2026-07-28T15:20:00Z"),
			ticket("ticket-10037", "SC-10037", "PHONE", "何汀", "北辰影像实验室", "PREMIUM",
				"批量导出任务一直停留在处理中", "约 18 万条记录的导出任务 EXP-78421 已停留在处理中 46 分钟。",
				"DATA_EXPORT", "HIGH", "READY_FOR_REVIEW", null, "2026-07-28T04:52:00Z", "2026-07-28T12:10:00Z"),
			ticket("ticket-10034", "SC-10034", "WEB_FORM", "顾予安", "衡木零售研究", "STANDARD",
				"专业版可以添加多少位协作者", "正在评估从基础版升级，想确认专业版的成员上限，以及新增成员如何计费。",
				"SUBSCRIPTION", "LOW", "NEW", null, "2026-07-28T03:38:00Z", "2026-07-29T02:00:00Z"),
			ticket("ticket-10031", "SC-10031", "EMAIL", "邵知夏", "杉禾教育科技", "ENTERPRISE",
				"申请导出并删除离职员工数据", "一名员工已经离职，我们需要导出该账号产生的内容并完成数据删除。",
				"PRIVACY", "HIGH", "NEEDS_ESCALATION", "陆予", "2026-07-27T23:20:00Z", "2026-07-28T13:30:00Z"),
			ticket("ticket-10026", "SC-10026", "CHAT", "孟桥", "澄明会计师事务所", "PREMIUM",
				"客户端提示错误码 SYNC-2047", "Windows 客户端同步失败，提示 SYNC-2047，重启客户端和网络后仍然出现。",
				"TECHNICAL", "MEDIUM", "WAITING_CUSTOMER", "陈屿", "2026-07-27T18:46:00Z", "2026-07-28T17:50:00Z"),
			ticket("ticket-10018", "SC-10018", "WEB_FORM", "唐见微", "弦月文化传播", "STANDARD",
				"能否恢复三个月前删除的项目", "团队成员三个月前误删了一个项目，现在发现归档里也没有，是否还能从备份恢复？",
				"DATA_RECOVERY", "MEDIUM", "READY_FOR_MANUAL_REVIEW", null, "2026-07-27T14:12:00Z", "2026-07-29T05:10:00Z")
		);

		ticketRepository.saveAll(tickets);
		tickets.stream().filter(ticket -> !"NEW".equals(ticket.getStatus())).forEach(analysisService::seed);
	}

	private Ticket ticket(
		String id,
		String ticketNo,
		String channel,
		String customerName,
		String customerCompany,
		String customerTier,
		String subject,
		String description,
		String category,
		String priority,
		String status,
		String assignee,
		String createdAt,
		String slaDeadline
	) {
		var ticket = new Ticket();
		ticket.setId(id);
		ticket.setTicketNo(ticketNo);
		ticket.setChannel(channel);
		ticket.setCustomerName(customerName);
		ticket.setCustomerCompany(customerCompany);
		ticket.setCustomerTier(customerTier);
		ticket.setSubject(subject);
		ticket.setDescription(description);
		ticket.setLanguage("zh-CN");
		ticket.setCategory(category);
		ticket.setPriority(priority);
		ticket.setStatus(status);
		ticket.setAssigneeName(assignee);
		ticket.setSlaDeadline(Instant.parse(slaDeadline));
		ticket.setCreatedAt(Instant.parse(createdAt));
		ticket.setUpdatedAt(Instant.parse(createdAt));
		return ticket;
	}
}
