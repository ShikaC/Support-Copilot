package com.cyagent.supportcopilot.ticket;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "tickets")
@Getter
@Setter
@NoArgsConstructor
public class Ticket {

	@Id
	private String id;

	@Column(nullable = false, unique = true, length = 32)
	private String ticketNo;

	@Column(nullable = false, length = 32)
	private String channel;

	@Column(nullable = false, length = 80)
	private String customerName;

	@Column(nullable = false, length = 120)
	private String customerCompany;

	@Column(nullable = false, length = 32)
	private String customerTier;

	@Column(nullable = false, length = 240)
	private String subject;

	@Column(nullable = false, length = 4000)
	private String description;

	@Column(nullable = false, length = 16)
	private String language;

	@Column(nullable = false, length = 48)
	private String category;

	@Column(nullable = false, length = 16)
	private String priority;

	@Column(nullable = false, length = 48)
	private String status;

	@Column(length = 80)
	private String assigneeName;

	@Column(nullable = false)
	private Instant slaDeadline;

	@Column(nullable = false, updatable = false)
	private Instant createdAt;

	@Column(nullable = false)
	private Instant updatedAt;

	@Version
	private long version;
}
