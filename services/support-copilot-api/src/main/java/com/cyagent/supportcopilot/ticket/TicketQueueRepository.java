package com.cyagent.supportcopilot.ticket;

import java.util.List;

public interface TicketQueueRepository {
	List<Ticket> findQueuePage(TicketQueueQuery query, TicketQueueCursor cursor, int limit);
	long countQueue(TicketQueueQuery query);
}
